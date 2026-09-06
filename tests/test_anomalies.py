"""Tests de non-régression sur les anomalies constatées dans les données sources.

Chaque anomalie a été mesurée par comptage avant correction. Les tests ci-dessous
vérifient que la correction tient, sur de petites tables construites ici — donc
sans dépendre de la présence de `data/raw/`.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from etl.clean import construire_uid, normaliser_typequ, strip_strings


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
