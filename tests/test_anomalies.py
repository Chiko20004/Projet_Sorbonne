"""Tests de non-régression sur les anomalies constatées dans les données sources.

Chaque anomalie a été mesurée par comptage avant correction. Les tests ci-dessous
vérifient que la correction tient, sur de petites tables construites ici — donc
sans dépendre de la présence de `data/raw/`.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from config import FONCTIONS, OSM_TYPEQU_CORRESPONDANCE
from etl.clean import (
    COLONNES_CLASSEES,
    _appliquer_classification,
    construire_uid,
    load_classification,
    normaliser_typequ,
    strip_strings,
)


def _equipements(lignes: list[dict]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        lignes, geometry=[Point(3.69, 43.4)] * len(lignes), crs="EPSG:4326"
    )


def test_strip_strings_nettoie_les_colonnes_de_dtype_str():
    """Anomalie 5 : sous pandas 3 les colonnes texte ont le dtype `str` et non
    `object`. Le test d'origine les laissait passer, et les noms de quartier
    gardaient leur padding de 100 caractères dans data/processed/."""
    gdf = gpd.GeoDataFrame(
        {"nom": pd.Series(["Canal entre 2 mers" + " " * 82], dtype="str")},
        geometry=[Point(3.69, 43.4)],
        crs="EPSG:4326",
    )
    assert gdf["nom"].dtype != object, "le cas testé suppose une colonne de dtype str"

    assert strip_strings(gdf)["nom"].iloc[0] == "Canal entre 2 mers"


def test_strip_strings_laisse_les_colonnes_numeriques_intactes():
    gdf = gpd.GeoDataFrame(
        {"population": [1234.5], "nom": ["  Sète  "]},
        geometry=[Point(3.69, 43.4)],
        crs="EPSG:4326",
    )
    nettoye = strip_strings(gdf)
    assert nettoye["population"].iloc[0] == 1234.5
    assert nettoye["nom"].iloc[0] == "Sète"


def test_uid_separe_deux_couches_qui_partagent_un_id():
    """Anomalie 1 : les couches ajoutées après coup (OSM_BUS, AJOUT_MANUEL,
    OSM_PARC, OSM_COWORK) repartent d'un compteur à 1 et percutent les codes BPE.
    Préfixer par la couche source sépare les deux équipements."""
    gdf = _equipements([
        {"id": 105, "typequ": "A504", "nom": "Boulangerie du port"},
        {"id": 105, "typequ": "OSM_BUS", "nom": "Arret de bus"},
    ])
    uid = construire_uid(gdf, "bpe")
    assert uid.tolist() == ["bpe-A504-105", "bpe-OSM_BUS-105"]


def test_uid_separe_une_collision_interne_a_une_couche():
    """25 groupes gardent le même code ET le même id. Leur nom les sépare, et
    l'ordre des noms rend le suffixe stable d'une exécution à l'autre."""
    gdf = _equipements([
        {"id": 105, "typequ": "OSM_BUS", "nom": "Arret de bus"},
        {"id": 105, "typequ": "OSM_BUS", "nom": "4819902722"},
    ])
    uid = construire_uid(gdf, "bpe")
    assert sorted(uid) == ["bpe-OSM_BUS-105", "bpe-OSM_BUS-105-2"]
    assert uid.is_unique
    # Le même jeu dans l'autre sens donne les mêmes identifiants.
    inverse = construire_uid(_equipements(list(reversed(gdf.drop(columns="geometry").to_dict("records")))), "bpe")
    assert dict(zip(gdf["nom"], uid)) == dict(zip(reversed(gdf["nom"].tolist()), inverse))


def test_normaliser_typequ_rend_le_code_utilisable_en_url():
    assert normaliser_typequ("A504") == "A504"
    assert normaliser_typequ("institut de beauté, onglerie") == "INSTITUT_DE_BEAUTE_ONGLERIE"
    assert normaliser_typequ(None) == "INCONNU"
    assert normaliser_typequ("   ") == "INCONNU"


def test_correspondance_osm_couvre_les_codes_du_fichier():
    """Anomalie 2 : le fichier OSM code OSM1/OSM2/OSM3, la classification nomme
    OSM_BUS/OSM_COWORK/OSM_PARC. Sans table de traduction, le recouvrement est
    nul et les 662 équipements OSM perdent fonction et niveau."""
    assert set(OSM_TYPEQU_CORRESPONDANCE) == {"OSM1", "OSM2", "OSM3"}
    assert set(OSM_TYPEQU_CORRESPONDANCE.values()) == {"OSM_BUS", "OSM_COWORK", "OSM_PARC"}


def _classification(lignes: list[dict]) -> pd.DataFrame:
    """Table de classification minimale, indexée sur typequ comme la vraie."""
    colonnes = {c: False for c in COLONNES_CLASSEES if c != "niveau"}
    df = pd.DataFrame([{**colonnes, "libelle_typequ": "", **ligne} for ligne in lignes])
    return df.set_index("typequ")


def test_la_classification_prime_sur_les_booleens_du_fichier():
    """Anomalie 4 : le fichier d'équipements se contredit lui-même. Ses booléens
    divergent de la classification sur 1 400 lignes pour proximite, alors que sa
    colonne niveau est d'accord avec elle sur la totalité des lignes."""
    equipements = _equipements([
        {"typequ": "A504", "proximite": 1.0, "intermediaire": 0.0, "habiter": 1.0, "niveau": "intermediaire"},
    ])
    classification = _classification([
        {"typequ": "A504", "proximite": False, "intermediaire": True, "niveau": "intermediaire"},
    ])
    resultat = _appliquer_classification(equipements, classification)
    assert bool(resultat["proximite"].iloc[0]) is False
    assert bool(resultat["intermediaire"].iloc[0]) is True
    assert resultat["niveau"].iloc[0] == "intermediaire"
    assert bool(resultat["habiter"].iloc[0]) is False


def test_un_code_classe_de_deux_facons_arrete_l_etl(tmp_path):
    """A304 est saisi deux fois dans la table fournie, mais avec les mêmes
    drapeaux : seul le libellé diffère, on garde la première ligne. Un vrai
    désaccord, lui, ne doit pas passer en silence."""
    entete = "typequ;libelle_typequ;proximite;intermediaire;centralite;" + ";".join(FONCTIONS) + ";prioritaire"
    faux = ["False"] * (len(FONCTIONS) + 3)
    csv_path = tmp_path / "bpe24key_classification.csv"

    lignes = [f"A304;ÉCOLE DE CONDUITE;{';'.join(faux)};True", f"A304;école de conduite;{';'.join(faux)};True"]
    csv_path.write_text("\n".join([entete, *lignes]), encoding="utf-8")
    table = load_classification(tmp_path)
    assert list(table.index) == ["A304"]
    assert table.loc["A304", "libelle_typequ"] == "ÉCOLE DE CONDUITE"

    divergent = [f"A304;école de conduite;True;{';'.join(faux[1:])};True", f"A304;école de conduite;{';'.join(faux)};True"]
    csv_path.write_text("\n".join([entete, *divergent]), encoding="utf-8")
    with pytest.raises(ValueError, match="A304"):
        load_classification(tmp_path)
