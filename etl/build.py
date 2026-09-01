"""Point d'entrée de l'ETL : `python -m etl.build`.

Lit les fichiers bruts (config.RAW_DATA_DIR), nettoie/harmonise, comble les
trous ponctuels par agrégation spatiale réelle, convertit le fichier
d'isochrones (122 Mo) en GeoPackage indexé, et écrit tout dans
config.PROCESSED_DATA_DIR. Ne fabrique aucune donnée absente des sources.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import PROCESSED_DATA_DIR, RAW_DATA_DIR, ISOCHRONE_SIMPLIFY_TOLERANCE
from etl import clean, isochrones, scores


def log(msg: str) -> None:
    print(f"[etl] {msg}", flush=True)


def main() -> None:
    t0 = time.time()
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    log("chargement classification.csv")
    classification = clean.load_classification(RAW_DATA_DIR)

    log("chargement équipements (bpe + osm)")
    equipements = clean.load_equipements(RAW_DATA_DIR, classification)
    equipements.to_file(PROCESSED_DATA_DIR / "equipements.geojson", driver="GeoJSON")
    log(f"  -> {len(equipements)} équipements")

    log("chargement bâtiments")
    batiments = clean.load_batiments(RAW_DATA_DIR)
    batiments.to_file(PROCESSED_DATA_DIR / "batiments.geojson", driver="GeoJSON")
    log(f"  -> {len(batiments)} bâtiments")

    log("chargement quartiers + comblement driving_car via bâtiments")
    quartiers = clean.load_quartiers(RAW_DATA_DIR)
    quartiers = scores.fill_missing_quartier_driving(quartiers, batiments)
    quartiers.to_file(PROCESSED_DATA_DIR / "quartiers.geojson", driver="GeoJSON")
    log(f"  -> {len(quartiers)} quartiers")

    for res in ("200m", "50m"):
        log(f"chargement grille {res}")
        grille = clean.load_grille(RAW_DATA_DIR, res)
        if res == "200m":
            log("  rattachement quartier_id (base du score pondéré par densité)")
            grille = scores.assign_quartier_id(grille, quartiers)
        grille.to_file(PROCESSED_DATA_DIR / f"grille_{res}.geojson", driver="GeoJSON")
        log(f"  -> {len(grille)} cellules")

    log("classification (json, pour légendes/tooltips)")
    classification.reset_index().to_json(
        PROCESSED_DATA_DIR / "classification.json", orient="records", force_ascii=False
    )

    log("conversion isochrones (122 Mo) -> GeoPackage indexé + simplifié")
    isochrones.build_isochrones_store(
        RAW_DATA_DIR / "isochrones_walking_15min.geojson",
        PROCESSED_DATA_DIR / "isochrones.gpkg",
        ISOCHRONE_SIMPLIFY_TOLERANCE,
    )
    size_mb = (PROCESSED_DATA_DIR / "isochrones.gpkg").stat().st_size / 1e6
    log(f"  -> isochrones.gpkg ({size_mb:.1f} Mo)")

    meta = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "raw_data_dir": str(RAW_DATA_DIR),
        "duration_seconds": round(time.time() - t0, 1),
    }
    (PROCESSED_DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    log(f"terminé en {meta['duration_seconds']}s")


if __name__ == "__main__":
    main()
