"""Rattachements spatiaux entre les couches, calculés à partir des géométries.

Un comblement des scores voiture des quartiers par jointure spatiale des
bâtiments a existé ici. Il ne s'est jamais déclenché : les colonnes
score_hqvs_driving_car_15 et _30 sont présentes sur les sept quartiers fournis.
Retiré plutôt que gardé en réserve, parce qu'un code jamais exécuté n'est pas
un filet de sécurité, c'est une supposition non vérifiée.
"""
from __future__ import annotations

import geopandas as gpd


def assign_quartier_id(grille: gpd.GeoDataFrame, quartiers: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Rattache chaque cellule de grille au conseil de quartier qui contient son
    centroïde. C'est ce rattachement qui permet d'agréger les cellules de la
    grille 200 m par quartier, plutôt que de faire confiance aux chiffres
    pré-agrégés du fichier de quartiers, calculés par une autre méthode.
    """
    grille = grille.copy()
    centroids = gpd.GeoDataFrame(
        grille[["id"]], geometry=grille.geometry.centroid, crs=grille.crs
    )
    joined = gpd.sjoin(
        centroids,
        quartiers[["id", "geometry"]].rename(columns={"id": "quartier_id"}),
        predicate="within",
        how="left",
    )
    joined = joined.drop_duplicates(subset="id")
    grille = grille.merge(joined[["id", "quartier_id"]], on="id", how="left")
    return grille
