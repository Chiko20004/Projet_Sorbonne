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
    assert all(f["properties"]["uid"] for f in habiter_only)


def test_api_isochrone_available_for_known_equipement(client):
    resp = client.get("/api/isochrone/bpe-A133-1")
    assert resp.status_code == 200
    assert resp.get_json()["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_api_isochrone_distingue_les_identifiants_en_collision(client):
    """L'id source 1 est porté par deux équipements sans rapport : la déchèterie
    de Sète (A133) et un arrêt de bus (OSM_BUS). L'ancienne route, qui cherchait
    par cet entier, en servait un des deux au hasard."""
    decheterie = client.get("/api/isochrone/bpe-A133-1").get_json()
    arret = client.get("/api/isochrone/bpe-OSM_BUS-1").get_json()
    assert decheterie["properties"]["equipement_uid"] == "bpe-A133-1"
    assert arret["properties"]["equipement_uid"] == "bpe-OSM_BUS-1"
    # Le calcul amont ayant lui aussi regroupé sur l'identifiant ambigu, ces deux
    # contours sont le même polygone fusionné. La route sert désormais la bonne
    # ligne, et cette ligne dit qu'elle n'est pas fiable.
    assert decheterie["properties"]["geometrie_fusionnee"] is True
    assert arret["properties"]["geometrie_fusionnee"] is True


def test_api_isochrone_ne_signale_pas_les_contours_sains(client):
    resp = client.get("/api/isochrone/bpe-A301-4").get_json()
    assert resp["properties"]["geometrie_fusionnee"] is False


def test_api_isochrone_404_for_unknown_id(client):
    assert client.get("/api/isochrone/999999999").status_code == 404
    assert client.get("/api/isochrone/bpe-A133-999999").status_code == 404


def test_api_equipements_se_limite_a_sete(client):
    """Le fichier source couvre toute l'agglomération : la carte ne doit servir
    que les équipements sétois."""
    tous = client.get("/api/equipements").get_json()["features"]
    assert all(f["properties"]["quartier_id"] is not None for f in tous)
    assert len(tous) == 2666


def test_api_equipements_filtre_par_territoire(client):
    tous = client.get("/api/equipements").get_json()["features"]
    un_quartier = client.get("/api/equipements?territoire=1").get_json()["features"]
    assert 0 < len(un_quartier) < len(tous)
    assert all(str(f["properties"]["quartier_id"]) == "1" for f in un_quartier)


def test_le_panneau_affiche_un_compteur_qui_suit_la_rosace(client):
    """Invariant : le clic sur un secteur met à jour le score ET le nombre
    d'équipements."""
    sans = client.get("/exploration/panel?mode=walking&duree=15").data
    avec = client.get("/exploration/panel?mode=walking&duree=15&fonction=habiter").data
    assert "Équipements".encode() in sans
    assert sans != avec
