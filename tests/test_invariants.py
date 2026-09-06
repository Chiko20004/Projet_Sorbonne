"""Tests des invariants imposés par la commande.

Ils portent sur ce que l'interface doit faire — rosace, radar, compteur
d'équipements — et non sur les anomalies des données, qui sont dans
`test_anomalies.py`. Les tables sont construites ici, donc ces tests tournent
sans `data/raw/`.
"""
from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Point, Polygon

from etl.scores import rattacher_au_quartier

# Deux quartiers voisins, chacun un carré d'environ 1 km de côté.
QUARTIERS = gpd.GeoDataFrame(
    {"id": ["q1", "q2"], "nom": ["Nord", "Sud"]},
    geometry=[
        Polygon([(3.69, 43.41), (3.70, 43.41), (3.70, 43.42), (3.69, 43.42)]),
        Polygon([(3.69, 43.40), (3.70, 43.40), (3.70, 43.41), (3.69, 43.41)]),
    ],
    crs="EPSG:4326",
)


def test_rattacher_au_quartier_place_chaque_point_dans_son_polygone():
    equipements = gpd.GeoDataFrame(
        {"uid": ["bpe-A-1", "bpe-A-2"]},
        geometry=[Point(3.695, 43.415), Point(3.695, 43.405)],
        crs="EPSG:4326",
    )
    resultat = rattacher_au_quartier(equipements, QUARTIERS, cle="uid")
    assert resultat.set_index("uid")["quartier_id"].to_dict() == {
        "bpe-A-1": "q1",
        "bpe-A-2": "q2",
    }


def test_rattacher_au_quartier_laisse_vide_ce_qui_tombe_dehors():
    """Le fichier d'équipements couvre toute l'agglomération : Montpellier, Agde
    et Frontignan pèsent chacun plus lourd que Sète. 14 720 des 17 386
    équipements sont hors des sept conseils de quartier. C'est un cas normal,
    qu'il faut savoir distinguer d'une erreur de rattachement."""
    equipements = gpd.GeoDataFrame(
        {"uid": ["bpe-A-1", "bpe-A-3"]},
        geometry=[Point(3.695, 43.415), Point(3.88, 43.61)],  # le second à Montpellier
        crs="EPSG:4326",
    )
    resultat = rattacher_au_quartier(equipements, QUARTIERS, cle="uid").set_index("uid")
    assert resultat.loc["bpe-A-1", "quartier_id"] == "q1"
    assert resultat["quartier_id"].isna().sum() == 1


def test_rattacher_au_quartier_marche_aussi_sur_des_polygones():
    """Le même calcul sert aux cellules de grille : le centroïde d'un point étant
    le point lui-même, une seule fonction couvre les deux usages."""
    cellules = gpd.GeoDataFrame(
        {"id": ["c1"]},
        geometry=[Polygon([(3.694, 43.414), (3.696, 43.414), (3.696, 43.416), (3.694, 43.416)])],
        crs="EPSG:4326",
    )
    resultat = rattacher_au_quartier(cellules, QUARTIERS)
    assert resultat["quartier_id"].iloc[0] == "q1"
