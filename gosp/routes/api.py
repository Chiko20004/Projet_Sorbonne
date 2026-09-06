from flask import Blueprint, jsonify, request

from gosp.services import data_store, scoring

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/map-layer")
def map_layer():
    unite = request.args.get("unite", "grille_200m")
    mode = request.args.get("mode", "walking")
    duree = request.args.get("duree", "15")
    key = scoring.score_key(mode, duree)

    if unite == "quartier":
        source = data_store.get_quartiers()
    elif unite == "grille_50m":
        source = data_store.get_grille("grille_50m")
    else:
        source = data_store.get_grille("grille_200m")

    features = []
    for feat in source["features"]:
        p = feat["properties"]
        features.append({
            "type": "Feature",
            "geometry": feat["geometry"],
            "properties": {
                "id": p.get("id"),
                "nom": p.get("nom"),
                "score": p.get(key),
                "population": p.get("population"),
                "peuplee": p.get("peuplee", True),
            },
        })
    return jsonify({"type": "FeatureCollection", "features": features})


@bp.get("/equipements")
def equipements():
    fonction = request.args.get("fonction") or None
    niveau = request.args.get("niveau") or None
    territoire = request.args.get("territoire") or None
    return jsonify(scoring.filter_equipements(fonction, niveau, territoire))


@bp.get("/isochrone/<equipement_uid>")
def isochrone(equipement_uid: str):
    feature = data_store.get_isochrone(equipement_uid)
    if feature is None:
        return jsonify({"error": "isochrone_introuvable"}), 404
    return jsonify(feature)
