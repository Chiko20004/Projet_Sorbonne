import pytest

from gosp import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("path", [
    "/", "/methodologie", "/documentation", "/exploration", "/quartiers/",
])
def test_pages_return_200(client, path):
    assert client.get(path).status_code == 200


def test_exploration_panel_fragment(client):
    resp = client.get("/exploration/panel?mode=walking&duree=15")
    assert resp.status_code == 200
    assert b"score-panel" in resp.data


def test_exploration_panel_reacts_to_mode_change(client):
    walking = client.get("/exploration/panel?mode=walking&duree=15").data
    driving = client.get("/exploration/panel?mode=driving_car&duree=15").data
    assert walking != driving


def test_quartier_detail_and_404(client):
    ok = client.get("/quartiers/1")
    assert ok.status_code == 200
    missing = client.get("/quartiers/does-not-exist")
    assert missing.status_code == 404


def test_api_map_layer_is_geojson(client):
    resp = client.get("/api/map-layer?unite=grille_200m&mode=walking&duree=15")
    data = resp.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0


def test_api_equipements_filter_by_fonction(client):
    all_eq = client.get("/api/equipements").get_json()["features"]
    habiter_only = client.get("/api/equipements?fonction=habiter").get_json()["features"]
    assert len(habiter_only) < len(all_eq)
    assert all(f["properties"]["id"] for f in habiter_only)


def test_api_isochrone_available_for_known_equipement(client):
    resp = client.get("/api/isochrone/1")
    assert resp.status_code == 200
    assert resp.get_json()["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_api_isochrone_404_for_unknown_id(client):
    resp = client.get("/api/isochrone/999999999")
    assert resp.status_code == 404
