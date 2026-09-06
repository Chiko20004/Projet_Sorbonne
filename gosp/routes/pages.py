from flask import Blueprint, render_template

from config import FONCTIONS_LABELS, MODE_LABELS, NIVEAU_LABELS, UNITE_LABELS
from gosp.services import data_store

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    quartiers = data_store.get_quartiers()["features"]
    return render_template("index.html", quartiers=quartiers)


@bp.get("/methodologie")
def methodologie():
    return render_template(
        "methodologie.html",
        fonctions=FONCTIONS_LABELS,
        modes=MODE_LABELS,
        niveaux=NIVEAU_LABELS,
        unites=UNITE_LABELS,
        comptes=data_store.get_comptes(),
    )


@bp.get("/documentation")
def documentation():
    return render_template("documentation.html")
