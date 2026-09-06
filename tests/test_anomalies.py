"""Tests de non-régression sur les anomalies constatées dans les données sources.

Chaque anomalie a été mesurée par comptage avant correction. Les tests ci-dessous
vérifient que la correction tient, sur de petites tables construites ici — donc
sans dépendre de la présence de `data/raw/`.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from etl.clean import strip_strings


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
