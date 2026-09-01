import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Dossier contenant les fichiers geojson/csv bruts fournis par la Chaire ETI.
RAW_DATA_DIR = Path(os.environ.get("GOSP_RAW_DATA_DIR", BASE_DIR / "data" / "raw"))

# Dossier de sortie de l'ETL (généré par `python -m etl.build`, gitignoré).
PROCESSED_DATA_DIR = Path(os.environ.get("GOSP_PROCESSED_DATA_DIR", BASE_DIR / "data" / "processed"))

SECRET_KEY = os.environ.get("GOSP_SECRET_KEY", "dev-key-change-in-production")

# Tolérance de simplification des géométries d'isochrones, en degrés (~5m à cette latitude).
ISOCHRONE_SIMPLIFY_TOLERANCE = float(os.environ.get("GOSP_ISOCHRONE_SIMPLIFY_TOLERANCE", "0.00005"))

FONCTIONS = [
    "habiter",
    "etre_en_forme",
    "apprendre",
    "s_epanouir",
    "travailler",
    "s_approvisionner",
]

FONCTIONS_LABELS = {
    "habiter": "Habiter",
    "etre_en_forme": "Être en forme",
    "apprendre": "Apprendre",
    "s_epanouir": "S'épanouir",
    "travailler": "Travailler",
    "s_approvisionner": "S'approvisionner",
}

MODES = ["walking", "cycling", "driving_car"]

MODE_LABELS = {
    "walking": "Marche",
    "cycling": "Vélo",
    "driving_car": "Voiture",
}

DUREES = [15, 30]

NIVEAUX_PROXIMITE = ["proximite", "intermediaire", "centralite"]

NIVEAU_LABELS = {
    "proximite": "Local",
    "intermediaire": "Intermédiaire",
    "centralite": "Centralité",
}

UNITES_SPATIALES = ["grille_200m", "grille_50m", "quartier"]

UNITE_LABELS = {
    "grille_200m": "Grille 200 m (recommandé)",
    "grille_50m": "Grille 50 m (détaillé)",
    "quartier": "Conseils de quartier",
}

# Axes du radar/rosace : 6 secteurs égaux, en partant du haut (12h), sens horaire.
import math as _math

RADAR_AXES = [
    (fonction, round(_math.cos(_math.radians(-90 + i * 60)), 4), round(_math.sin(_math.radians(-90 + i * 60)), 4))
    for i, fonction in enumerate(FONCTIONS)
]

def _unit(angle_deg):
    return round(_math.cos(_math.radians(angle_deg)), 4), round(_math.sin(_math.radians(angle_deg)), 4)

ROSACE_WEDGES = [
    (fonction, _unit(-90 + i * 60 - 30), _unit(-90 + i * 60 + 30))
    for i, fonction in enumerate(FONCTIONS)
]
