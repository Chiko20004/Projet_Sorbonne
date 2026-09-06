"""Tests de non-régression sur les anomalies constatées dans les données sources.

Chaque anomalie a été mesurée par comptage avant correction. Les tests ci-dessous
vérifient que la correction tient, sur de petites tables construites ici — donc
sans dépendre de la présence de `data/raw/`.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from config import DUREE_REFERENCE, FONCTIONS, MODE_REFERENCE, OSM_TYPEQU_CORRESPONDANCE
from etl.clean import (
    COLONNES_CLASSEES,
    _appliquer_classification,
    construire_uid,
    load_classification,
    rattraper_par_libelle,
    normaliser_typequ,
    strip_strings,
    ajouter_surface_et_densite,
)
from etl import scores
from gosp.services import data_store, presentation, scoring


def _equipements(lignes: list[dict]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        lignes, geometry=[Point(3.69, 43.4)] * len(lignes), crs="EPSG:4326"
    )


def test_strip_strings_nettoie_les_colonnes_de_dtype_str():
    """Anomalie 5 : sous pandas 3 les colonnes texte ont le dtype `str` et non
    `object`. Le test d'origine les laissait passer, et les noms de quartier
    gardaient leur padding de 100 caractères dans data/processed/."""
    gdf = gpd.GeoDataFrame(
        {"nom": pd.Series(["Canal entre 2 mers" + " " * 82], dtype="str")},
        geometry=[Point(3.69, 43.4)],
        crs="EPSG:4326",
    )
    assert gdf["nom"].dtype != object, "le cas testé suppose une colonne de dtype str"

    assert strip_strings(gdf)["nom"].iloc[0] == "Canal entre 2 mers"


def test_strip_strings_laisse_les_colonnes_numeriques_intactes():
    gdf = gpd.GeoDataFrame(
        {"population": [1234.5], "nom": ["  Sète  "]},
        geometry=[Point(3.69, 43.4)],
        crs="EPSG:4326",
    )
    nettoye = strip_strings(gdf)
    assert nettoye["population"].iloc[0] == 1234.5
    assert nettoye["nom"].iloc[0] == "Sète"


def test_uid_separe_deux_couches_qui_partagent_un_id():
    """Anomalie 1 : les couches ajoutées après coup (OSM_BUS, AJOUT_MANUEL,
    OSM_PARC, OSM_COWORK) repartent d'un compteur à 1 et percutent les codes BPE.
    Préfixer par la couche source sépare les deux équipements."""
    gdf = _equipements([
        {"id": 105, "typequ": "A504", "nom": "Boulangerie du port"},
        {"id": 105, "typequ": "OSM_BUS", "nom": "Arret de bus"},
    ])
    uid = construire_uid(gdf, "bpe")
    assert uid.tolist() == ["bpe-A504-105", "bpe-OSM_BUS-105"]


def test_uid_separe_une_collision_interne_a_une_couche():
    """25 groupes gardent le même code ET le même id. Leur nom les sépare, et
    l'ordre des noms rend le suffixe stable d'une exécution à l'autre."""
    gdf = _equipements([
        {"id": 105, "typequ": "OSM_BUS", "nom": "Arret de bus"},
        {"id": 105, "typequ": "OSM_BUS", "nom": "4819902722"},
    ])
    uid = construire_uid(gdf, "bpe")
    assert sorted(uid) == ["bpe-OSM_BUS-105", "bpe-OSM_BUS-105-2"]
    assert uid.is_unique
    # Le même jeu dans l'autre sens donne les mêmes identifiants.
    inverse = construire_uid(_equipements(list(reversed(gdf.drop(columns="geometry").to_dict("records")))), "bpe")
    assert dict(zip(gdf["nom"], uid)) == dict(zip(reversed(gdf["nom"].tolist()), inverse))


def test_normaliser_typequ_rend_le_code_utilisable_en_url():
    assert normaliser_typequ("A504") == "A504"
    assert normaliser_typequ("institut de beauté, onglerie") == "INSTITUT_DE_BEAUTE_ONGLERIE"
    assert normaliser_typequ(None) == "INCONNU"
    assert normaliser_typequ("   ") == "INCONNU"


def test_correspondance_osm_couvre_les_codes_du_fichier():
    """Anomalie 2 : le fichier OSM code OSM1/OSM2/OSM3, la classification nomme
    OSM_BUS/OSM_COWORK/OSM_PARC. Sans table de traduction, le recouvrement est
    nul et les 662 équipements OSM perdent fonction et niveau."""
    assert set(OSM_TYPEQU_CORRESPONDANCE) == {"OSM1", "OSM2", "OSM3"}
    assert set(OSM_TYPEQU_CORRESPONDANCE.values()) == {"OSM_BUS", "OSM_COWORK", "OSM_PARC"}


def _classification(lignes: list[dict]) -> pd.DataFrame:
    """Table de classification minimale, indexée sur typequ comme la vraie."""
    colonnes = {c: False for c in COLONNES_CLASSEES}
    colonnes["niveau"] = None
    df = pd.DataFrame([{**colonnes, "libelle_typequ": "", **ligne} for ligne in lignes])
    return df.set_index("typequ")


def test_la_classification_prime_sur_les_booleens_du_fichier():
    """Anomalie 4 : le fichier d'équipements se contredit lui-même. Ses booléens
    divergent de la classification sur 1 400 lignes pour proximite, alors que sa
    colonne niveau est d'accord avec elle sur la totalité des lignes."""
    equipements = _equipements([
        {"typequ": "A504", "typequ_classe": "A504", "proximite": 1.0,
         "intermediaire": 0.0, "habiter": 1.0, "niveau": "proximite"},
    ])
    classification = _classification([
        {"typequ": "A504", "proximite": False, "intermediaire": True, "niveau": "intermediaire"},
    ])
    resultat = _appliquer_classification(equipements, classification)
    assert bool(resultat["proximite"].iloc[0]) is False
    assert bool(resultat["intermediaire"].iloc[0]) is True
    assert resultat["niveau"].iloc[0] == "intermediaire"
    assert bool(resultat["habiter"].iloc[0]) is False


def test_un_code_classe_de_deux_facons_arrete_l_etl(tmp_path):
    """A304 est saisi deux fois dans la table fournie, mais avec les mêmes
    drapeaux : seul le libellé diffère, on garde la première ligne. Un vrai
    désaccord, lui, ne doit pas passer en silence."""
    entete = "typequ;libelle_typequ;proximite;intermediaire;centralite;" + ";".join(FONCTIONS) + ";prioritaire"
    faux = ["False"] * (len(FONCTIONS) + 3)
    csv_path = tmp_path / "bpe24key_classification.csv"

    lignes = [f"A304;ÉCOLE DE CONDUITE;{';'.join(faux)};True", f"A304;école de conduite;{';'.join(faux)};True"]
    csv_path.write_text("\n".join([entete, *lignes]), encoding="utf-8")
    table = load_classification(tmp_path)
    assert list(table.index) == ["A304"]
    assert table.loc["A304", "libelle_typequ"] == "ÉCOLE DE CONDUITE"

    divergent = [f"A304;école de conduite;True;{';'.join(faux[1:])};True", f"A304;école de conduite;{';'.join(faux)};True"]
    csv_path.write_text("\n".join([entete, *divergent]), encoding="utf-8")
    with pytest.raises(ValueError, match="A304"):
        load_classification(tmp_path)


def test_rattrapage_par_libelle_quand_le_code_est_inconnu():
    """Anomalie 3 : 89 équipements portent le code AJOUT_MANUEL, absent de la
    classification, mais un libellé qui y figure mot pour mot."""
    classification = _classification([
        {"typequ": "B203", "libelle_typequ": "boulangerie, pâtisserie", "proximite": True},
    ])
    gdf = _equipements([
        {"typequ": "AJOUT_MANUEL", "libelle_typequ": "boulangerie, pâtisserie"},
        {"typequ": "AJOUT_MANUEL", "libelle_typequ": "centre social"},
        {"typequ": "B203", "libelle_typequ": "boulangerie, pâtisserie"},
    ])
    resolus = rattraper_par_libelle(gdf, classification)
    assert resolus.tolist() == ["B203", "AJOUT_MANUEL", "B203"]


def test_les_equipements_non_classes_sont_marques():
    """On ne les fait pas passer pour des équipements sans fonction : on dit que
    leur classement est inconnu, ce qui n'est pas la même chose."""
    classification = _classification([{"typequ": "B203", "habiter": True}])
    gdf = _equipements([
        {"typequ": "B203", "typequ_classe": "B203"},
        {"typequ": "E101", "typequ_classe": "E101"},
    ])
    resultat = _appliquer_classification(gdf, classification)
    assert resultat["classe"].tolist() == [True, False]
    assert bool(resultat["habiter"].iloc[0]) is True
    assert pd.isna(resultat["habiter"].iloc[1])


def test_le_radar_ne_rabote_pas_la_combinaison_de_reference(monkeypatch):
    """Anomalie 6 : le rapport divisait par score_global, moyenne des six scores
    de fonction sans mode ni durée. À Saint Clair il valait 0,307, donc le radar
    rabotait les six fonctions de 69 % — en marche 15 min, sur la vue par défaut,
    là où il n'y a précisément rien à approximer."""
    cellules = [{
        "peuplee": True, "population": 100.0, "quartier_id": "1",
        "score_global": 5.38, "score_walking_15": 1.65, "score_cycling_30": 3.30,
        **{f"score_{f}": 5.0 for f in FONCTIONS},
    }]
    monkeypatch.setattr(scoring.data_store, "get_grille",
                        lambda _: {"features": [{"properties": c} for c in cellules]})

    reference = scoring.radar("1", MODE_REFERENCE, DUREE_REFERENCE)
    assert reference["ratio_approximation"] == 1.0
    assert reference["est_approximation"] is False
    assert all(v == 5.0 for v in reference["valeurs"].values())

    # Hors référence, la mise à l'échelle reste relative à la marche 15 min.
    autre = scoring.radar("1", "cycling", 30)
    assert autre["ratio_approximation"] == 2.0
    assert autre["est_approximation"] is True
    assert all(v == 10.0 for v in autre["valeurs"].values())


def test_la_surface_est_calculee_depuis_la_geometrie():
    """Anomalie 7 : surf_km2 est vide sur les sept quartiers fournis, alors que
    le panneau annonce une pondération par la densité. On la mesure en Lambert 93,
    où une aire se lit en mètres."""
    carre_1km = Polygon([(3.69, 43.40), (3.702, 43.40), (3.702, 43.409), (3.69, 43.409)])
    gdf = gpd.GeoDataFrame(
        {"population": [2000.0], "surf_km2": [None]}, geometry=[carre_1km], crs="EPSG:4326"
    )
    resultat = ajouter_surface_et_densite(gdf)
    surface = resultat["surf_km2"].iloc[0]
    assert 0.9 < surface < 1.1, surface
    assert resultat["densite_hab_km2"].iloc[0] == round(2000.0 / surface, 1)


def test_ponderation_par_densite_et_par_population_coincident_sur_une_grille(monkeypatch):
    """Toutes les cellules de la grille 200 m ont la même surface : y pondérer par
    la densité ou par la population donne le même chiffre. L'écart n'apparaît
    qu'entre unités de tailles différentes, comme les quartiers."""
    cellules = [
        {"peuplee": True, "population": 1000.0, "surf_km2": 0.04, "densite_hab_km2": 25000.0,
         "score_walking_15": 2.0},
        {"peuplee": True, "population": 10.0, "surf_km2": 0.04, "densite_hab_km2": 250.0,
         "score_walking_15": 8.0},
    ]
    monkeypatch.setattr(scoring.data_store, "get_grille",
                        lambda _: {"features": [{"properties": c} for c in cellules]})
    panneau = scoring.score_panel(None, "walking", 15)

    assert panneau["pondere"] == scoring._weighted_mean(cellules, "score_walking_15", "population")
    assert panneau["pondere"] < panneau["brut"]
    assert panneau["surface_km2"] == 0.08
    assert panneau["densite_hab_km2"] == 12625.0


def test_la_couche_batiments_n_est_plus_chargee_au_demarrage():
    """Anomalie 9 : 8,8 Mo parsés à chaque démarrage de Flask, qu'aucune route ni
    aucun gabarit ne lit. La couche reste une entrée d'ETL."""
    source = Path(data_store.__file__).read_text(encoding="utf-8")
    debut = source.index("def load_all()")
    assert '"batiments"' not in source[debut:source.index("def get_layer")]


def test_le_comblement_voiture_mort_a_ete_retire():
    """Anomalie 8 : la fonction ne se déclenchait jamais, les colonnes voiture
    étant présentes sur les sept quartiers."""
    assert not hasattr(scores, "fill_missing_quartier_driving")


@pytest.mark.parametrize("valeur, decimales, attendu", [
    (5.02, 2, "5,02"),
    (4099, 0, "4 099"),
    (43643.5, 0, "43 644"),
    (1.594, 3, "1,594"),
    (0.7133, 2, "0,71"),
    (None, 2, "—"),
])
def test_nombre_ecrit_a_la_francaise(valeur, decimales, attendu):
    """Convention du projet : virgule décimale, espace comme séparateur de
    milliers, tiret quand la donnée manque."""
    assert presentation.nombre(valeur, decimales) == attendu
