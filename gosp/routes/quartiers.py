from flask import Blueprint, abort, render_template

from gosp.routes.exploration import _build_panel_context, _parse_filters
from gosp.services import data_store

bp = Blueprint("quartiers", __name__, url_prefix="/quartiers")


@bp.get("/")
def list_quartiers():
    return render_template("quartiers/list.html", quartiers=data_store.get_quartiers()["features"])


@bp.get("/<quartier_id>")
def detail(quartier_id: str):
    quartier = data_store.find_quartier(quartier_id)
    if quartier is None:
        abort(404)
    filters = _parse_filters({"territoire": quartier_id})
    ctx = _build_panel_context(filters)
    return render_template("quartiers/detail.html", **ctx)
