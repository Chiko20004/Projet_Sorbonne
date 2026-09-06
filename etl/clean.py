"""Chargement et nettoyage des fichiers geojson/csv bruts fournis par la Chaire ETI.

Aucune donnée n'est inventée ici : ce module ne fait que réparer un encodage
mal interprété (mojibake réversible, voir `fix_mojibake`) et harmoniser les
noms de colonnes entre les différents fichiers sources (qui n'utilisent pas
tous les mêmes conventions, ex. `score_hqvs_moyen` vs `score_hqvs_global`).
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd

from config import FONCTIONS, OSM_TYPEQU_CORRESPONDANCE

SCORE_FONCTION_COLS = [f"score_{f}" for f in FONCTIONS]
# Lambert 93 : projection légale en France métropolitaine, où une aire se mesure
# en mètres. Calculer une surface directement en degrés n'aurait pas de sens.
CRS_METRIQUE = 2154
# Colonnes dont la table de classification est la source, pas le fichier d'équipements.
COLONNES_CLASSEES = ["proximite", "intermediaire", "centralite", "prioritaire", "niveau"] + FONCTIONS
MODE_DUREE_COMBOS = [
    ("walking", 15), ("walking", 30),
    ("cycling", 15), ("cycling", 30),
    ("driving_car", 15), ("driving_car", 30),
]


def _colonne_texte(serie: pd.Series) -> bool:
    """Vrai pour une colonne susceptible de contenir des chaînes.

    Le test ne peut pas se limiter à `dtype == object` : sous pandas 3 les
    colonnes texte ont le dtype `str`, et un tel test laisse passer tout le
    padding des exports sources.
    """
    return serie.dtype == object or pd.api.types.is_string_dtype(serie)


def strip_strings(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Certains exports (ex. conseils_quartier_hqvs.geojson) stockent les
    chaînes avec un padding fixe ('La Lagune' + espaces jusqu'à largeur fixe).
    On les nettoie systématiquement plutôt qu'au cas par cas."""
    for col in gdf.columns:
        if col != "geometry" and _colonne_texte(gdf[col]):
            gdf[col] = gdf[col].map(lambda v: v.strip() if isinstance(v, str) else v)
    return gdf


def fix_mojibake(value):
    """Répare l'encodage des champs texte des exports BPE/OSM.

    Constat (vérifié sur bpe24_equipements.geojson et isochrones_walking_15min.geojson) :
    les chaînes accentuées ont été décodées en Latin-1 alors que les octets sont
    de l'UTF-8 valide (ex. "SÃ\\x88TE" doit être lu comme les octets UTF-8 de
    "SÈTE"). Le motif est systématique et se répare donc sans perte via un
    aller-retour latin-1 -> utf-8. Si la chaîne ne suit pas ce motif (déjà
    propre), on la renvoie inchangée plutôt que de risquer de la corrompre.
    """
    if not isinstance(value, str) or not value:
        return value
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return value
    return repaired


def normaliser_typequ(valeur) -> str:
    """Ramène un code typequ à [A-Z0-9_], pour qu'il tienne dans un identifiant
    d'URL. Un seul code du jeu fourni en a besoin ('institut de beauté,
    onglerie'), mais rien ne garantit qu'un millésime suivant soit plus propre.
    """
    if not isinstance(valeur, str) or not valeur.strip():
        return "INCONNU"
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFKD", valeur.strip().upper())
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Z0-9]+", "_", sans_accent).strip("_") or "INCONNU"


def construire_uid(gdf: gpd.GeoDataFrame, fichier: str) -> pd.Series:
    """Identifiant stable d'équipement, de la forme `<fichier>-<typequ>-<id source>`.

    L'id source seul ne suffit pas : quatre couches ajoutées après coup dans
    bpe24_equipements.geojson (OSM_BUS, AJOUT_MANUEL, OSM_PARC, OSM_COWORK)
    repartent chacune d'un compteur à 1 et percutent les codes BPE officiels.
    396 identifiants sont ainsi portés par deux équipements distincts, ce qui
    faisait servir la mauvaise isochrone. Préfixer par la couche source, et non
    par le fichier d'origine, en résout 371.

    Les 25 collisions restantes sont internes à une couche : deux équipements y
    partagent le même code ET le même id. On les sépare par leur nom, qui diffère
    toujours, en suffixant les suivants -2, -3… L'ordre est celui des noms, donc
    l'identifiant reste le même d'une exécution de l'ETL à l'autre.
    """
    base = (
        fichier + "-" + gdf["typequ"].map(normaliser_typequ) + "-" + gdf["id"].astype(str)
    )
    rang = (
        pd.DataFrame({"base": base, "nom": gdf.get("nom", pd.Series(index=gdf.index)).fillna("").astype(str)})
        .sort_values(["base", "nom"], kind="stable")
        .groupby("base")
        .cumcount()
        .reindex(gdf.index)
    )
    return base.where(rang == 0, base + "-" + (rang + 1).astype(str))


def _derive_niveau(row) -> str | None:
    if row.get("centralite"):
        return "centralite"
    if row.get("intermediaire"):
        return "intermediaire"
    if row.get("proximite"):
        return "proximite"
    return None


def load_classification(raw_dir: Path) -> pd.DataFrame:
    """Charge bpe24key_classification.csv (typequ -> libellé + flags fonction/niveau).

    NB : l'extrait fourni ne contient pas les colonnes poids_hqvs / tier_rarete
    présentes dans la base de production. Cette pondération par rareté
    d'équipement n'est donc pas implémentée ici — voir /methodologie.
    """
    path = raw_dir / "bpe24key_classification.csv"
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = [h.strip() for h in next(reader)]
        rows = [[c.strip() for c in row] for row in reader if row]
    df = pd.DataFrame(rows, columns=header)

    bool_cols = ["proximite", "intermediaire", "centralite"] + FONCTIONS + ["prioritaire"]
    for col in bool_cols:
        df[col] = df[col].map({"True": True, "False": False, "": False}).fillna(False)

    df["niveau"] = df.apply(_derive_niveau, axis=1)

    # A304 « école de conduite » est saisi deux fois, à la casse du libellé près.
    # Les drapeaux étant identiques, la ligne en trop ne change que le libellé
    # affiché et on garde la première. Un doublon qui classerait le même code de
    # deux façons différentes, lui, demanderait un arbitrage : mieux vaut alors
    # s'arrêter que d'en retenir un au hasard.
    doublons = df[df["typequ"].duplicated(keep=False)]
    if not doublons.empty:
        distincts = doublons.drop(columns=["libelle_typequ"]).drop_duplicates()
        if len(distincts) != doublons["typequ"].nunique():
            raise ValueError(
                "Codes typequ classés de deux façons différentes : "
                + ", ".join(sorted(doublons["typequ"].unique()))
            )
        df = df.drop_duplicates(subset="typequ", keep="first")

    return df.set_index("typequ")


def _compter_divergences(gdf: gpd.GeoDataFrame, classification: pd.DataFrame) -> dict:
    """Compare les booléens portés par le fichier d'équipements à ceux de la
    classification, sur les seules lignes dont le code est connu. C'est ce
    comptage qui justifie de ne garder qu'une source."""
    connus = gdf[gdf["typequ"].isin(classification.index)]
    if connus.empty:
        return {}
    table = connus.join(classification[COLONNES_CLASSEES], on="typequ", rsuffix="_cls")
    comptes = {"equipements_a_code_connu": len(connus)}
    for col in ["proximite", "intermediaire", "centralite"]:
        if col in connus.columns:
            fichier = table[col].fillna(0).astype(bool)
            reference = table[f"{col}_cls"].astype(bool)
            comptes[f"divergences_{col}"] = int((fichier != reference).sum())
    if "niveau" in connus.columns:
        ecart = table["niveau"].notna() & (table["niveau"] != table["niveau_cls"])
        comptes["divergences_niveau"] = int(ecart.sum())
    return comptes


def rattraper_par_libelle(gdf: gpd.GeoDataFrame, classification: pd.DataFrame) -> pd.Series:
    """Code de classement des équipements dont le `typequ` est inconnu de la table
    mais dont le libellé y figure mot pour mot.

    89 équipements portent le code `AJOUT_MANUEL`, qui n'est pas un code BPE.
    Leur libellé, lui, en est un : « boulangerie, pâtisserie », « pharmacie »,
    « coiffure »… Les rattacher par ce libellé n'invente rien, c'est la même
    chaîne de caractères des deux côtés. Deux libellés restent dehors, « centre
    social » et « papeterie et press », qui n'ont pas d'équivalent exact : on ne
    les corrige pas à la main.
    """
    par_libelle = (
        classification.reset_index()
        .assign(_l=lambda d: d["libelle_typequ"].str.strip().str.casefold())
        .drop_duplicates(subset="_l", keep="first")
        .set_index("_l")["typequ"]
    )
    inconnus = ~gdf["typequ"].isin(classification.index)
    libelles = gdf["libelle_typequ"].where(inconnus).str.strip().str.casefold()
    return libelles.map(par_libelle).fillna(gdf["typequ"])


def _appliquer_classification(gdf: gpd.GeoDataFrame, classification: pd.DataFrame) -> gpd.GeoDataFrame:
    """Fait de la table de classification la source unique du niveau de proximité
    et des six fonctions.

    Le fichier d'équipements porte ses propres booléens, qui contredisent la
    table sur 1 400 lignes pour `proximite` (11,1 % des codes connus), 1 390 pour
    `intermediaire` et 266 pour `centralite`. Sa colonne `niveau`, elle, est
    d'accord avec la table sur la totalité des lignes. C'est donc la table qui
    fait foi, et s'en tenir à elle évite d'arbitrer ligne à ligne entre deux
    versions de la même information.
    """
    gdf = gdf.drop(columns=[c for c in COLONNES_CLASSEES if c in gdf.columns])
    gdf = gdf.join(classification[COLONNES_CLASSEES], on="typequ_classe")
    # 4 099 équipements gardent un code que la table ne connaît pas et n'ont donc
    # ni niveau ni fonction. Les classer demanderait la nomenclature BPE, absente
    # des sources fournies. On le marque au lieu de les laisser passer pour des
    # équipements sans fonction, ce qui n'est pas la même chose.
    gdf["classe"] = gdf["typequ_classe"].isin(classification.index)
    return gdf


def load_equipements(raw_dir: Path, classification: pd.DataFrame) -> gpd.GeoDataFrame:
    """Combine bpe24_equipements.geojson (source principale) et osm_equipements.geojson
    (complémentaire). Les deux tirent leur niveau et leurs fonctions de la même
    table de classification, jointe sur typequ.
    """
    text_cols = ["nom", "commune", "libelle_typequ"]

    bpe = gpd.read_file(raw_dir / "bpe24_equipements.geojson").reset_index(drop=True)
    for col in text_cols:
        if col in bpe.columns:
            bpe[col] = bpe[col].map(fix_mojibake)
    bpe["source"] = "bpe"
    bpe["id_source"] = bpe["id"]
    bpe["uid"] = construire_uid(bpe, "bpe")
    comptes = _compter_divergences(bpe, classification)
    bpe["typequ_classe"] = rattraper_par_libelle(bpe, classification)
    bpe = _appliquer_classification(bpe, classification)

    osm = gpd.read_file(raw_dir / "osm_equipements.geojson").reset_index(drop=True)
    osm["libelle_typequ"] = osm["libelle_typequ"].map(fix_mojibake)
    # `typequ` garde ce que dit le fichier ; `typequ_classe` porte le code sous
    # lequel la table de classification connaît l'équipement. Sans cette
    # traduction, la jointure OSM ne rattache rien (voir OSM_TYPEQU_CORRESPONDANCE).
    osm["typequ_classe"] = osm["typequ"].map(OSM_TYPEQU_CORRESPONDANCE).fillna(osm["typequ"])
    osm["nom"] = None
    osm["commune"] = None
    osm["code_postal"] = None
    osm["source"] = "osm"
    osm["id_source"] = osm["id"]
    osm["uid"] = construire_uid(osm, "osm")
    osm = _appliquer_classification(osm, classification)

    keep_cols = [
        "uid", "id_source", "typequ", "typequ_classe", "libelle_typequ", "nom", "commune", "code_postal",
        "proximite", "intermediaire", "centralite", "niveau", "prioritaire", "classe",
        "source", "geometry",
    ] + FONCTIONS

    bpe = bpe[[c for c in keep_cols if c in bpe.columns]]
    osm = osm[[c for c in keep_cols if c in osm.columns]]

    combined = pd.concat([bpe, osm], ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    # Le libellé de la classification fait autorité : le fichier OSM orthographie
    # le même parc de trois façons (« Par et jardin », « Parc et jardin »,
    # « parcs et jardins »). À défaut, on garde celui du fichier, puis le code.
    depuis_table = combined["typequ_classe"].map(classification["libelle_typequ"])
    combined["libelle_typequ"] = depuis_table.fillna(combined["libelle_typequ"]).fillna(combined["typequ"])

    combined = strip_strings(combined)
    combined.attrs["comptes"] = comptes
    return combined


def ajouter_surface_et_densite(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Calcule la surface depuis la géométrie, puis en déduit la densité.

    `surf_km2` est vide sur les sept quartiers fournis, alors que le panneau de
    score annonce une pondération par la densité de population : l'indicateur
    était annoncé sans jamais être calculé. On mesure donc l'aire en Lambert 93
    (EPSG:2154), projection conforme où une surface se lit en mètres — la
    calculer en degrés donnerait un nombre sans signification.

    Si un millésime suivant renseigne `surf_km2`, la valeur calculée ici lui
    servira de contrôle plutôt que de remplacement.
    """
    gdf = gdf.copy()
    gdf["surf_km2"] = (gdf.geometry.to_crs(CRS_METRIQUE).area / 1e6).round(4)
    population = pd.to_numeric(gdf["population"], errors="coerce")
    gdf["densite_hab_km2"] = (population / gdf["surf_km2"]).round(1)
    return gdf


def _rename_scores(gdf: gpd.GeoDataFrame, global_col_candidates: list[str]) -> gpd.GeoDataFrame:
    for candidate in global_col_candidates:
        if candidate in gdf.columns:
            gdf = gdf.rename(columns={candidate: "score_global"})
            break
    for mode, duree in MODE_DUREE_COMBOS:
        src = f"score_hqvs_{mode}_{duree}"
        if src in gdf.columns:
            gdf = gdf.rename(columns={src: f"score_{mode}_{duree}"})
    return gdf


def load_batiments(raw_dir: Path) -> gpd.GeoDataFrame:
    """Seule couche portant une population et un score par bâtiment.

    Elle n'alimente aujourd'hui aucune sortie : l'agrégation se fait sur la
    grille 200 m. Le chargeur reste ici parce que le fichier fait partie des
    sources attendues par scripts/fetch_data.sh, et que le rattachement à un
    découpage IRIS en aura besoin.
    """
    gdf = gpd.read_file(raw_dir / "batiments_hqvs.geojson")
    gdf = gdf.rename(columns={"batiment_id": "id", "population_batiment": "population"})
    gdf = _rename_scores(gdf, ["score_hqvs_global"])
    return strip_strings(gdf)


def load_grille(raw_dir: Path, resolution: str) -> gpd.GeoDataFrame:
    """resolution: '50m' ou '200m'. Fusionne les cellules peuplées (avec scores)
    et non peuplées (géométrie seule, affichées en gris sur la carte)."""
    peuplees = gpd.read_file(raw_dir / f"grille_{resolution}_peuplees.geojson")
    non_peuplees = gpd.read_file(raw_dir / f"grille_{resolution}_non_peuplees.geojson")

    peuplees = peuplees.rename(columns={"poly_id": "id", "pop_batiments": "population"})
    peuplees = _rename_scores(peuplees, ["score_hqvs_moyen"])
    peuplees["peuplee"] = True

    non_peuplees = non_peuplees.rename(columns={"poly_id": "id"})
    non_peuplees["peuplee"] = False
    non_peuplees["population"] = 0.0

    combined = pd.concat([peuplees, non_peuplees], ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs="EPSG:4326")
    return strip_strings(ajouter_surface_et_densite(combined))


def load_quartiers(raw_dir: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(raw_dir / "conseils_quartier_hqvs.geojson")
    gdf = gdf.rename(columns={"poly_id": "id", "nom_quartier": "nom"})
    gdf = _rename_scores(gdf, ["score_hqvs_moyen"])
    # population_ref (population de référence externe, ex. INSEE) est vide sur les
    # sept quartiers fournis. On retombe donc sur pop_batiments, calculée à partir
    # des bâtiments, qui reste une population réellement mesurée.
    gdf["population_ref"] = pd.to_numeric(gdf["population_ref"], errors="coerce")
    gdf["population"] = gdf["population_ref"].fillna(gdf["pop_batiments"])
    return strip_strings(ajouter_surface_et_densite(gdf))
