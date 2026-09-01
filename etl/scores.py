"""Comble les trous ponctuels de la donnée source par agrégation spatiale
authentique (jamais par valeur inventée).

Filet de sécurité : si une source de quartiers ne fournit pas les scores
score_hqvs_driving_car_15/30 (présents sur les grilles et les bâtiments),
on les recalcule par jointure spatiale des bâtiments
(batiments_hqvs.geojson, qui a la donnée voiture) dans chaque polygone de
quartier, avec une moyenne pondérée par la population du bâtiment. Le champ
booléen `driving_estime` marque les valeurs recalculées pour rester
transparent en interface.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np


def assign_quartier_id(grille: gpd.GeoDataFrame, quartiers: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Rattache chaque cellule de grille au conseil de quartier qui contient son
    centroïde. Sert de base au score HQVS pondéré par densité (décision 2 du
    plan) : on agrège les cellules de la grille 200 m avec une moyenne
    pondérée par leur population, plutôt que de faire confiance à une simple
    moyenne arithmétique de cellules à faible population.
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


def fill_missing_quartier_driving(quartiers: gpd.GeoDataFrame, batiments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    quartiers = quartiers.copy()
    missing_cols = [c for c in ("score_driving_car_15", "score_driving_car_30") if c not in quartiers.columns]
    if not missing_cols:
        quartiers["driving_estime"] = False
        return quartiers

    joined = gpd.sjoin(
        batiments[["id", "population", "score_driving_car_15", "score_driving_car_30", "geometry"]],
        quartiers[["id", "geometry"]].rename(columns={"id": "quartier_id"}),
        predicate="within",
        how="inner",
    )

    for col in missing_cols:
        weighted = (
            joined.assign(_w=joined[col] * joined["population"])
            .groupby("quartier_id")
            .agg(_wsum=("_w", "sum"), _psum=("population", "sum"))
        )
        weighted[col] = np.where(weighted["_psum"] > 0, weighted["_wsum"] / weighted["_psum"], np.nan)
        quartiers = quartiers.merge(
            weighted[[col]], left_on="id", right_index=True, how="left"
        )

    quartiers["driving_estime"] = True
    return quartiers
