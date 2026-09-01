"""Formules de score pour la page Exploration.

Toutes les agrégations (score pondéré par densité, radar par fonction) sont
calculées à partir de la grille 200 m (`services.data_store.get_grille`),
choisie comme unité statistique de référence (voir /methodologie) — que le
territoire demandé soit un quartier précis ou "toute la ville". Cela évite de
mélanger des chiffres pré-agrégés par des méthodes différentes selon la
source (quartier vs grille vs bâtiment).
"""
from __future__ import annotations

import math

from config import FONCTIONS
from gosp.services import data_store


def score_key(mode: str, duree: int) -> str:
    return f"score_{mode}_{duree}"


def _populated_cells(quartier_id: str | None = None) -> list[dict]:
    grille = data_store.get_grille("grille_200m")
    cells = []
    for feat in grille["features"]:
        props = feat["properties"]
        if not props.get("peuplee") or not props.get("population"):
            continue
        if quartier_id is not None and str(props.get("quartier_id")) != str(quartier_id):
            continue
        cells.append(props)
    return cells


def _arithmetic_mean(cells: list[dict], key: str) -> float | None:
    values = [c[key] for c in cells if c.get(key) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _weighted_mean(cells: list[dict], key: str, weight_key: str = "population") -> float | None:
    num, den = 0.0, 0.0
    for c in cells:
        v, w = c.get(key), c.get(weight_key)
        if v is None or not w:
            continue
        num += v * w
        den += w
    if den == 0:
        return None
    return round(num / den, 2)


def score_panel(quartier_id: str | None, mode: str, duree: int) -> dict:
    """Le score 'pondéré' est une moyenne
    pondérée par la population des cellules, distincte du score 'brut'
    (moyenne arithmétique simple), pour qu'une zone peu peuplée à score élevé
    ne pèse pas autant qu'une zone dense au même score."""
    cells = _populated_cells(quartier_id)
    key = score_key(mode, duree)
    population_totale = sum(c["population"] for c in cells if c.get("population"))
    return {
        "brut": _arithmetic_mean(cells, key),
        "pondere": _weighted_mean(cells, key),
        "population_totale": round(population_totale, 1),
        "n_cellules": len(cells),
    }


def combined_duration_score(quartier_id: str | None, mode: str) -> float | None:
    """Moyenne géométrique entre 15 min et 30 min
    (proposition ouverte, pas une norme validée — pénalise un déséquilibre
    proximité locale / étendue plus qu'une moyenne arithmétique)."""
    cells = _populated_cells(quartier_id)
    s15 = _weighted_mean(cells, score_key(mode, 15))
    s30 = _weighted_mean(cells, score_key(mode, 30))
    if s15 is None or s30 is None or s15 < 0 or s30 < 0:
        return None
    return round(math.sqrt(s15 * s30), 2)


def radar(quartier_id: str | None, mode: str, duree: int) -> dict:
    """Les 6 scores par fonction (score_apprendre, etc.) n'existent dans les
    données sources que sous une forme non ventilée par mode/durée — il n'y a
    pas de matrice fonction x mode x durée. Approximation documentée
    (/methodologie) : on part de la valeur de référence par fonction, mise à
    l'échelle par le ratio entre le score global du mode/durée sélectionné et
    le score global de référence, pour refléter le changement de niveau
    d'accessibilité sans inventer une ventilation qui n'existe pas."""
    cells = _populated_cells(quartier_id)
    reference = {f: _weighted_mean(cells, f"score_{f}") for f in FONCTIONS}
    ref_global = _weighted_mean(cells, "score_global")
    target_global = _weighted_mean(cells, score_key(mode, duree))

    ratio = 1.0
    if ref_global and target_global is not None:
        ratio = target_global / ref_global

    approx = {}
    for f, v in reference.items():
        approx[f] = None if v is None else round(min(10.0, max(0.0, v * ratio)), 2)

    return {
        "reference": reference,
        "valeurs": approx,
        "ratio_approximation": round(ratio, 3),
        "est_approximation": duree != 15 or mode != "walking",
    }


def filter_equipements(fonction: str | None, niveau: str | None) -> dict:
    layer = data_store.get_equipements()
    features = layer["features"]
    if fonction:
        features = [f for f in features if f["properties"].get(fonction)]
    if niveau:
        features = [f for f in features if f["properties"].get("niveau") == niveau]
    return {"type": "FeatureCollection", "features": features}
