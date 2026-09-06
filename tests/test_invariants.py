"""Tests des invariants imposés par la commande.

Ils portent sur ce que l'interface doit faire — rosace, radar, compteur
d'équipements — et non sur les anomalies des données, qui sont dans
`test_anomalies.py`. Les tables sont construites ici, donc ces tests tournent
sans `data/raw/`.
"""
from __future__ import annotations

import re

import geopandas as gpd
from shapely.geometry import Point, Polygon

from config import FONCTIONS, FONCTIONS_LABELS, RADAR_AXES
from etl.scores import rattacher_au_quartier
from gosp import create_app
from gosp.services import scoring

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


def _couche(equipements: list[dict]) -> dict:
    return {"features": [{"type": "Feature", "properties": p} for p in equipements]}


ECHANTILLON = [
    # Deux équipements sétois, l'un « habiter » de proximité, l'autre non classé.
    {"uid": "bpe-A-1", "quartier_id": "q1", "niveau": "proximite", "habiter": 1.0},
    {"uid": "bpe-A-2", "quartier_id": "q1", "niveau": None},
    # Un équipement dans l'autre quartier.
    {"uid": "bpe-A-3", "quartier_id": "q2", "niveau": "centralite", "travailler": 1.0},
    # Un équipement de l'agglomération, hors des sept conseils de quartier.
    {"uid": "bpe-A-4", "quartier_id": None, "niveau": "proximite", "habiter": 1.0},
]


def test_le_compteur_ecarte_les_equipements_hors_sete(monkeypatch):
    """Le fichier couvre l'agglomération. Un compte annoncé comme sétois ne doit
    pas inclure Montpellier."""
    monkeypatch.setattr(scoring.data_store, "get_equipements", lambda: _couche(ECHANTILLON))
    assert scoring.compter_equipements(None, None)["total"] == 3
    uids = [f["properties"]["uid"] for f in scoring.filter_equipements(None, None)["features"]]
    assert "bpe-A-4" not in uids


def test_le_compteur_suit_la_fonction_le_niveau_et_le_territoire(monkeypatch):
    """Invariant : un clic sur un secteur de la rosace met à jour le score et le
    nombre d'équipements."""
    monkeypatch.setattr(scoring.data_store, "get_equipements", lambda: _couche(ECHANTILLON))
    assert scoring.compter_equipements("habiter", None)["total"] == 1
    assert scoring.compter_equipements("travailler", None)["total"] == 1
    assert scoring.compter_equipements(None, "proximite")["total"] == 1
    assert scoring.compter_equipements(None, None, "q1")["total"] == 2
    assert scoring.compter_equipements("habiter", None, "q2")["total"] == 0


def test_le_compteur_annonce_a_part_les_equipements_sans_fonction(monkeypatch):
    """Ces équipements disparaissent dès qu'un secteur est actif : n'afficher que
    le total ferait mentir le compteur par omission."""
    monkeypatch.setattr(scoring.data_store, "get_equipements", lambda: _couche(ECHANTILLON))
    comptes = scoring.compter_equipements(None, None)
    assert comptes["sans_fonction"] == 1
    assert comptes["sur_le_territoire"] == 3


def test_la_carte_et_le_compteur_voient_le_meme_jeu(monkeypatch):
    """Ils passent par la même fonction de filtrage : ils ne peuvent pas diverger."""
    monkeypatch.setattr(scoring.data_store, "get_equipements", lambda: _couche(ECHANTILLON))
    for fonction, niveau, territoire in [
        (None, None, None), ("habiter", None, None), (None, "proximite", "q1"),
        ("travailler", "centralite", "q2"),
    ]:
        servis = scoring.filter_equipements(fonction, niveau, territoire)["features"]
        compte = scoring.compter_equipements(fonction, niveau, territoire)["total"]
        assert len(servis) == compte


def _rendre_radar(active_fonction):
    """Rend la macro seule, sans passer par une route."""
    app = create_app()
    with app.app_context():
        gabarit = app.jinja_env.from_string(
            '{% from "macros/svg.html" import radar_svg with context %}'
            "{{ radar_svg(valeurs, fonctions_labels, 260, active) }}"
        )
        return gabarit.render(
            valeurs={f: 5.0 for f in FONCTIONS},
            fonctions_labels=FONCTIONS_LABELS,
            active=active_fonction,
            radar_axes=RADAR_AXES,
            fonctions_labels_g=FONCTIONS_LABELS,
        )


def test_le_radar_met_en_evidence_la_fonction_cliquee():
    """Invariant : le radar doit mettre en évidence la fonction cliquée. Il ne
    recevait pas `active_fonction` du tout."""
    rendu = _rendre_radar("apprendre")
    axe = re.search(r'<line[^>]*data-fonction="apprendre"[^>]*>', rendu).group(0)
    point = re.search(r'<circle class="radar-point[^"]*"[^>]*data-fonction="apprendre"[^>]*>', rendu).group(0)
    libelle = re.search(r'<text[^>]*data-fonction="apprendre"[^>]*>', rendu).group(0)

    assert "radar-axe--actif" in axe
    assert "radar-point--actif" in point
    assert 'font-weight="700"' in libelle
    assert "radar-halo" in rendu


def test_le_radar_ne_signale_pas_la_fonction_active_par_la_seule_couleur():
    """L'accessibilité demandée interdit la couleur comme seul vecteur
    d'information : l'épaisseur, la taille et la graisse doivent aussi changer."""
    actif = _rendre_radar("apprendre")
    axe_actif = re.search(r'<line[^>]*data-fonction="apprendre"[^>]*>', actif).group(0)
    point_actif = re.search(r'<circle class="radar-point[^"]*"[^>]*data-fonction="apprendre"[^>]*>', actif).group(0)

    neutre = _rendre_radar(None)
    axe_neutre = re.search(r'<line[^>]*data-fonction="apprendre"[^>]*>', neutre).group(0)
    point_neutre = re.search(r'<circle class="radar-point[^"]*"[^>]*data-fonction="apprendre"[^>]*>', neutre).group(0)

    assert 'stroke-width="3"' in axe_actif and 'stroke-width="1"' in axe_neutre
    assert 'r="6"' in point_actif and 'r="3.5"' in point_neutre
    assert "radar-halo" not in neutre


def test_le_radar_nomme_la_fonction_active_pour_les_lecteurs_d_ecran():
    """Sans ça, la mise en évidence n'existe que pour ceux qui voient."""
    assert "Apprendre mise en évidence" in _rendre_radar("apprendre")
    assert "mise en évidence" not in _rendre_radar(None)
