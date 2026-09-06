from flask import Blueprint, render_template, request

from config import (
    DUREE_REFERENCE, DUREES, FONCTIONS, FONCTIONS_LABELS, MODE_LABELS, MODE_REFERENCE,
    MODES, NIVEAU_LABELS, NIVEAUX_PROXIMITE, UNITE_LABELS, UNITES_SPATIALES,
)
from gosp.services import data_store, scoring

bp = Blueprint("exploration", __name__)


def _parse_filters(args) -> dict:
    mode = args.get("mode", "walking")
    if mode not in MODES:
        mode = "walking"
    try:
        duree = int(args.get("duree", 15))
    except ValueError:
        duree = 15
    if duree not in DUREES:
        duree = 15
    unite = args.get("unite", "grille_200m")
    if unite not in UNITES_SPATIALES:
        unite = "grille_200m"
    fonction = args.get("fonction") or None
    if fonction not in FONCTIONS:
        fonction = None
    niveau = args.get("niveau") or None
    if niveau not in NIVEAUX_PROXIMITE:
        niveau = None
    territoire = args.get("territoire") or None  # None = toute la ville

    return {
        "mode": mode, "duree": duree, "unite": unite,
        "fonction": fonction, "niveau": niveau, "territoire": territoire,
    }


def _build_panel_context(filters: dict) -> dict:
    territoire = filters["territoire"]
    quartier = data_store.find_quartier(territoire) if territoire else None

    panel = scoring.score_panel(territoire, filters["mode"], filters["duree"])
    radar_data = scoring.radar(territoire, filters["mode"], filters["duree"])
    combinee = scoring.combined_duration_score(territoire, filters["mode"])
    equipements = scoring.compter_equipements(
        filters["fonction"], filters["niveau"], territoire
    )

    values = radar_data["valeurs"]
    ranked = sorted(
        ((f, v) for f, v in values.items() if v is not None), key=lambda kv: kv[1]
    )
    a_ameliorer = ranked[0] if ranked else None
    mieux_desservi = ranked[-1] if ranked else None

    return {
        "filters": filters,
        "quartier": quartier,
        "panel": panel,
        "equipements": equipements,
        "comptes": data_store.get_comptes(),
        "radar": radar_data,
        "combinee_15_30": combinee,
        "a_ameliorer": a_ameliorer,
        "mieux_desservi": mieux_desservi,
        "fonctions_labels": FONCTIONS_LABELS,
        "modes": MODE_LABELS,
        "niveaux": NIVEAU_LABELS,
        "isochrone_disponible": (filters["mode"], filters["duree"]) == (MODE_REFERENCE, DUREE_REFERENCE),
    }


@bp.get("/exploration")
def exploration():
    filters = _parse_filters(request.args)
    ctx = _build_panel_context(filters)
    return render_template(
        "exploration.html",
        quartiers=data_store.get_quartiers()["features"],
        durees=DUREES, unites=UNITE_LABELS, fonctions=FONCTIONS_LABELS,
        **ctx,
    )


@bp.get("/exploration/panel")
def exploration_panel():
    filters = _parse_filters(request.args)
    ctx = _build_panel_context(filters)
    return render_template("fragments/score_panel.html", **ctx)
