"""Conversion de isochrones_walking_15min.geojson (122 Mo, 16 785 polygones —
un par équipement) en GeoPackage local, simplifié et indexé.

Le fichier brut n'est jamais servi au navigateur ni chargé entièrement en
mémoire par Flask : on interroge le GeoPackage à la demande, un équipement
(ou une petite bbox) à la fois, via `services/data_store.py`.

C'est le SEUL fichier fournissant une géométrie d'isochrone réelle (marche,
15 min). Aucune géométrie n'existe pour les 5 autres combinaisons mode/durée
(marche 30, vélo 15/30, voiture 15/30) — voir la décision produit documentée
sur /methodologie : ces combinaisons n'affichent qu'une choroplèthe (scores
réels disponibles), sans contour d'isochrone.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import geopandas as gpd
import pandas as pd

from etl.clean import _colonne_texte, fix_mojibake

# Colonnes du fichier d'isochrones qui identifient l'équipement concerné.
# equipement_id seul ne suffit pas : il porte les mêmes collisions que le
# fichier d'équipements. Le triplet, lui, est unique des deux côtés.
CLE_EQUIPEMENT = ["typequ", "equipement_id", "nom"]


def _cle(df: pd.DataFrame, colonnes: list[str]) -> pd.Series:
    """Clé de jointure textuelle. Le mojibake est réparé des deux côtés (le
    fichier d'isochrones porte le même encodage cassé que celui des équipements)
    et les identifiants numériques sont ramenés à une écriture unique, sinon un
    105 entier et un 105.0 flottant ne se rejoignent pas."""
    parts = []
    for col in colonnes:
        serie = df[col]
        if _colonne_texte(serie):
            serie = serie.map(fix_mojibake).fillna("").astype(str).str.strip()
        else:
            serie = pd.to_numeric(serie, errors="coerce").astype("Int64").astype(str)
        parts.append(serie)
    return parts[0].str.cat(parts[1:], sep="\x1f")


def build_isochrones_store(
    raw_path: Path,
    out_path: Path,
    simplify_tolerance: float,
    equipements: gpd.GeoDataFrame,
) -> dict:
    """Écrit le GeoPackage et y ajoute `equipement_uid`, l'identifiant stable
    construit par `clean.construire_uid`. C'est cette colonne que la carte
    interroge : `equipement_id` est ambigu sur 792 lignes.

    Renvoie le comptage de la jointure, pour que l'ETL puisse le journaliser.
    """
    if out_path.exists():
        out_path.unlink()

    iso = gpd.read_file(raw_path)
    iso["geometry"] = iso.geometry.simplify(simplify_tolerance)

    # La collision d'identifiants ne s'arrête pas au fichier d'équipements : le
    # calcul des isochrones a lui aussi regroupé sur cet entier ambigu, et a donc
    # fusionné les contours de deux équipements sans rapport. Le comptage le
    # montre sans ambiguïté : les 15 872 lignes à identifiant unique ont toutes
    # une géométrie d'un seul tenant, alors que 787 des 913 lignes en collision
    # en ont deux, séparées de plusieurs kilomètres.
    #
    # Ces contours-là ne sont pas réparables ici : il faudrait relancer le calcul
    # amont sur des identifiants corrigés. On les marque pour que la carte le
    # dise au lieu de les afficher comme les autres.
    iso["geometrie_fusionnee"] = iso["equipement_id"].duplicated(keep=False)

    bpe = equipements[equipements["source"] == "bpe"]
    correspondance = pd.Series(
        bpe["uid"].values,
        index=_cle(bpe.rename(columns={"id_source": "equipement_id"}), CLE_EQUIPEMENT),
    )
    correspondance = correspondance[~correspondance.index.duplicated()]
    iso["equipement_uid"] = _cle(iso, CLE_EQUIPEMENT).map(correspondance)

    orphelines = int(iso["equipement_uid"].isna().sum())
    iso.to_file(out_path, driver="GPKG", layer="isochrones")

    # Index attributaire : la carte demande un isochrone par équipement cliqué,
    # sans index chaque requête scanne les 16 785 lignes.
    conn = sqlite3.connect(out_path)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_isochrones_uid ON isochrones(equipement_uid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_isochrones_typequ ON isochrones(typequ)")
        conn.commit()
    finally:
        conn.close()

    return {
        "isochrones": len(iso),
        "isochrones_sans_equipement": orphelines,
        "equipements_avec_isochrone": int(iso["equipement_uid"].nunique()),
        "isochrones_fusionnees": int(iso["geometrie_fusionnee"].sum()),
    }


# Le mojibake des champs nom/libelle_typequ n'est pas réparé dans le GeoPackage :
# les triggers d'intégrité géométrique GPKG bloquent les UPDATE sur ce texte sans
# SpatiaLite. Comme on ne sert qu'un isochrone à la fois, la réparation se fait à
# la réponse, dans services/data_store.py.
