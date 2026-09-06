"""Chargement unique des données traitées (data/processed/) au démarrage de
Flask, puis service en mémoire. Le GeoPackage d'isochrones (60 Mo, 16 785
polygones) n'est PAS chargé en mémoire : on interroge un équipement à la fois
à la demande, via geopandas/pyogrio avec un filtre attributaire.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import geopandas as gpd

from config import PROCESSED_DATA_DIR
from etl.clean import fix_mojibake

# L'uid arrive par l'URL et part dans une clause WHERE : on n'accepte que la
# forme produite par `clean.construire_uid`, rien d'autre.
UID_VALIDE = re.compile(r"[a-z]+-[A-Z0-9_]+-\d+(-\d+)?")

_layers: dict[str, dict] = {}
_classification: list[dict] = []


class DataNotBuiltError(RuntimeError):
    pass


def load_all() -> None:
    if not PROCESSED_DATA_DIR.exists() or not (PROCESSED_DATA_DIR / "meta.json").exists():
        raise DataNotBuiltError(
            f"Données traitées introuvables dans {PROCESSED_DATA_DIR}. "
            "Lancer d'abord : python -m etl.build"
        )
    for name in ("quartiers", "grille_200m", "grille_50m", "equipements", "batiments"):
        with open(PROCESSED_DATA_DIR / f"{name}.geojson", encoding="utf-8") as f:
            _layers[name] = json.load(f)

    global _classification
    with open(PROCESSED_DATA_DIR / "classification.json", encoding="utf-8") as f:
        _classification = json.load(f)


def get_layer(name: str) -> dict:
    return _layers[name]


def get_quartiers() -> dict:
    return _layers["quartiers"]


def get_grille(resolution: str) -> dict:
    """resolution: 'grille_200m' ou 'grille_50m'."""
    return _layers[resolution]


def get_equipements() -> dict:
    return _layers["equipements"]


def get_classification() -> list[dict]:
    return _classification


def find_quartier(quartier_id: str) -> dict | None:
    for feat in _layers["quartiers"]["features"]:
        if str(feat["properties"]["id"]) == str(quartier_id):
            return feat
    return None


def get_isochrone(equipement_uid: str) -> dict | None:
    """L'isochrone se cherche par identifiant stable, pas par l'id du fichier
    source : celui-ci est porté par deux équipements distincts sur 792 lignes et
    renvoyait donc parfois la géométrie d'un autre équipement."""
    if not UID_VALIDE.fullmatch(equipement_uid or ""):
        return None
    path = PROCESSED_DATA_DIR / "isochrones.gpkg"
    gdf = gpd.read_file(
        path, layer="isochrones", where=f"equipement_uid = '{equipement_uid}'"
    )
    if gdf.empty:
        return None
    feature = json.loads(gdf.to_json())["features"][0]
    props = feature["properties"]
    for key in ("nom", "libelle_typequ"):
        if key in props:
            props[key] = fix_mojibake(props[key])
    return feature
