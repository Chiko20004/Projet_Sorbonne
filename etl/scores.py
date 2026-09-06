"""Rattachements spatiaux entre les couches, calculés à partir des géométries.

Un comblement des scores voiture des quartiers par jointure spatiale des
bâtiments a existé ici. Il ne s'est jamais déclenché : les colonnes
score_hqvs_driving_car_15 et _30 sont présentes sur les sept quartiers fournis.
Retiré plutôt que gardé en réserve, parce qu'un code jamais exécuté n'est pas
un filet de sécurité, c'est une supposition non vérifiée.
"""
from __future__ import annotations

import geopandas as gpd

from etl.clean import CRS_METRIQUE


def rattacher_au_quartier(
    gdf: gpd.GeoDataFrame, quartiers: gpd.GeoDataFrame, cle: str = "id"
) -> gpd.GeoDataFrame:
    """Rattache chaque objet au conseil de quartier qui contient son centroïde.

    Sert pour les cellules de grille, ce qui permet d'agréger la grille 200 m par
    quartier plutôt que de faire confiance aux chiffres pré-agrégés du fichier de
    quartiers, calculés par une autre méthode. Sert aussi pour les équipements,
    qui doivent pouvoir être comptés quartier par quartier — le centroïde d'un
    point étant le point lui-même, le même calcul convient aux deux.

    `quartier_id` reste vide pour ce qui tombe hors des sept polygones : le
    fichier d'équipements couvre un périmètre plus large que les conseils de
    quartier. C'est un cas normal, pas une erreur, et l'ETL en donne le compte.
    """
    gdf = gdf.copy()
    # Le centroïde se calcule en Lambert 93 puis revient en WGS 84 : le prendre
    # directement sur des degrés donne un point légèrement décalé, et geopandas
    # a raison de s'en plaindre.
    centroides = gpd.GeoDataFrame(
        gdf[[cle]],
        geometry=gdf.geometry.to_crs(CRS_METRIQUE).centroid.to_crs(gdf.crs),
        crs=gdf.crs,
    )
    joined = gpd.sjoin(
        centroides,
        quartiers[["id", "geometry"]].rename(columns={"id": "quartier_id"}),
        predicate="within",
        how="left",
    )
    joined = joined.drop_duplicates(subset=cle)
    return gdf.merge(joined[[cle, "quartier_id"]], on=cle, how="left")
