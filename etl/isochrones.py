"""Conversion de isochrones_walking_15min.geojson (122 Mo, 16 785 polygones —
un par équipement) en GeoPackage local, simplifié et indexé.

Le fichier brut n'est jamais servi au navigateur ni chargé entièrement en
mémoire par Flask : on interroge le GeoPackage à la demande, un équipement
(ou une petite bbox) à la fois, via `services/data_store.py`.

C'est le SEUL fichier fournissant une géométrie d'isochrone réelle (marche,
15 min). Aucune géométrie n'existe pour les 5 autres combinaisons mode/durée
(marche 30, vélo 15/30, voiture 15/30) — voir la décision produit documentée
sur /methodologie : ces combinaisons n'affichent qu'une choroplèthe (scores
réels disponibles), sans contour d'isochrone.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
from pathlib import Path


def build_isochrones_store(raw_path: Path, out_path: Path, simplify_tolerance: float) -> None:
    if out_path.exists():
        out_path.unlink()

    subprocess.run(
        [
            "ogr2ogr",
            "-f", "GPKG", str(out_path), str(raw_path),
            "-simplify", str(simplify_tolerance),
            "-nln", "isochrones",
            "-nlt", "PROMOTE_TO_MULTI",
        ],
        check=True,
    )

    # Index attribut pour des lookups par équipement en O(log n) plutôt qu'un
    # scan complet des 16 785 lignes à chaque requête de carte.
    conn = sqlite3.connect(out_path)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_isochrones_equipement ON isochrones(equipement_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_isochrones_typequ ON isochrones(typequ)")
        conn.commit()
    finally:
        conn.close()


# NB : on ne répare pas le mojibake nom/libelle_typequ dans le GeoPackage lui-même
# (les triggers d'intégrité géométrique GPKG bloquent les UPDATE sur ce texte
# sans l'extension SpatiaLite). Comme on ne sert jamais qu'un isochrone à la
# fois, `clean.fix_mojibake` est appliqué au moment de la réponse, dans
# services/data_store.py — coût négligeable, pas de dépendance supplémentaire.
