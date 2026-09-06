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

from config import FONCTIONS, PROCESSED_DATA_DIR, RAW_DATA_DIR, ISOCHRONE_SIMPLIFY_TOLERANCE
from etl import clean, isochrones, scores


def log(msg: str) -> None:
    print(f"[etl] {msg}", flush=True)


def main() -> None:
    t0 = time.time()
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Les anomalies des données sources sont recomptées à chaque exécution plutôt
    # qu'écrites en dur quelque part : un changement de millésime doit faire bouger
    # les chiffres affichés sur /methodologie, pas les laisser mentir.
    comptes: dict[str, int] = {}

    log("chargement classification.csv")
    classification = clean.load_classification(RAW_DATA_DIR)

    # Les quartiers passent avant les équipements : ceux-ci doivent porter leur
    # quartier_id avant d'être écrits, pour être comptés quartier par quartier.
    log("chargement quartiers")
    quartiers = clean.load_quartiers(RAW_DATA_DIR)
    quartiers.to_file(PROCESSED_DATA_DIR / "quartiers.geojson", driver="GeoJSON")
    log(f"  -> {len(quartiers)} quartiers")

    log("chargement équipements (bpe + osm)")
    equipements = clean.load_equipements(RAW_DATA_DIR, classification)
    comptes_equipements = equipements.attrs.get("comptes", {})
    equipements = scores.rattacher_au_quartier(equipements, quartiers, cle="uid")
    equipements.attrs["comptes"] = comptes_equipements
    equipements.to_file(PROCESSED_DATA_DIR / "equipements.geojson", driver="GeoJSON")
    log(f"  -> {len(equipements)} équipements")

    # Le fichier couvre toute l'agglomération, pas Sète : Montpellier, Agde et
    # Frontignan y pèsent plus lourd que Sète elle-même. Ces équipements comptent
    # dans le calcul amont des isochrones — un Sétois peut être proche d'un
    # équipement situé au-delà de la limite communale — mais ils n'ont rien à
    # faire dans un compte annoncé comme sétois.
    comptes["equipements_dans_sete"] = int(equipements["quartier_id"].notna().sum())
    comptes["equipements_hors_sete"] = int(equipements["quartier_id"].isna().sum())
    log(f"  -> {comptes['equipements_dans_sete']} dans les sept conseils de quartier, "
        f"{comptes['equipements_hors_sete']} ailleurs dans l'agglomération")

    comptes.update(equipements.attrs.get("comptes", {}))
    log(f"  -> niveau : {comptes.get('divergences_niveau')} écart(s) entre le fichier "
        f"et la classification, sur {comptes.get('equipements_a_code_connu')} codes connus")
    log(f"  -> booléens du fichier écartés : {comptes.get('divergences_proximite')} sur proximite, "
        f"{comptes.get('divergences_intermediaire')} sur intermediaire, "
        f"{comptes.get('divergences_centralite')} sur centralite")

    comptes["equipements_non_classes"] = int((~equipements["classe"]).sum())
    comptes["equipements_rattrapes_par_libelle"] = int(
        (equipements["classe"] & (equipements["typequ"] != equipements["typequ_classe"])
         & (equipements["source"] == "bpe")).sum()
    )
    log(f"  -> {comptes['equipements_rattrapes_par_libelle']} rattrapés par leur libellé, "
        f"{comptes['equipements_non_classes']} restent sans fonction connue")

    osm = equipements[equipements["source"] == "osm"]
    comptes["equipements_osm"] = len(osm)
    comptes["equipements_osm_rattaches"] = int(
        osm[FONCTIONS].fillna(False).astype(bool).any(axis=1).sum()
    )
    log(f"  -> dont {comptes['equipements_osm']} OSM, "
        f"{comptes['equipements_osm_rattaches']} rattachés à une fonction")

    for res in ("200m", "50m"):
        log(f"chargement grille {res}")
        grille = clean.load_grille(RAW_DATA_DIR, res)
        if res == "200m":
            log("  rattachement quartier_id (base du score pondéré par densité)")
            grille = scores.rattacher_au_quartier(grille, quartiers)
        grille.to_file(PROCESSED_DATA_DIR / f"grille_{res}.geojson", driver="GeoJSON")
        log(f"  -> {len(grille)} cellules")

    log("classification (json, pour légendes/tooltips)")
    classification.reset_index().to_json(
        PROCESSED_DATA_DIR / "classification.json", orient="records", force_ascii=False
    )

    log("conversion isochrones (122 Mo) -> GeoPackage indexé + simplifié")
    comptes_isochrones = isochrones.build_isochrones_store(
        RAW_DATA_DIR / "isochrones_walking_15min.geojson",
        PROCESSED_DATA_DIR / "isochrones.gpkg",
        ISOCHRONE_SIMPLIFY_TOLERANCE,
        equipements,
    )
    size_mb = (PROCESSED_DATA_DIR / "isochrones.gpkg").stat().st_size / 1e6
    log(f"  -> isochrones.gpkg ({size_mb:.1f} Mo)")
    log(f"  -> {comptes_isochrones['equipements_avec_isochrone']} équipements rattachés, "
        f"{comptes_isochrones['isochrones_sans_equipement']} isochrones orphelines")
    log(f"  -> {comptes_isochrones['isochrones_fusionnees']} contours issus d'un "
        "identifiant ambigu, signalés dans l'interface")
    comptes.update(comptes_isochrones)

    meta = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "raw_data_dir": str(RAW_DATA_DIR),
        "duration_seconds": round(time.time() - t0, 1),
        "comptes": comptes,
    }
    (PROCESSED_DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    log(f"terminé en {meta['duration_seconds']}s")


if __name__ == "__main__":
    main()
