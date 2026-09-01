#!/usr/bin/env bash
# Récupère les fichiers sources dans data/raw/.
#
# Les données brutes (~140 Mo) ne sont pas versionnées : elles sont fournies par
# la Chaire ETI et ne nous appartiennent pas. Deux options selon le contexte.
#
#   1. Copie locale  : DATA_SRC=/chemin/vers/le/dossier ./scripts/fetch_data.sh
#   2. Archive HTTP  : DATA_URL=https://.../archive.zip ./scripts/fetch_data.sh
#
# Puis : python -m etl.build

set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw

REQUIS=(
  bpe24_equipements.geojson
  osm_equipements.geojson
  bpe24key_classification.csv
  batiments_hqvs.geojson
  conseils_quartier_hqvs.geojson
  grille_50m_peuplees.geojson
  grille_50m_non_peuplees.geojson
  grille_200m_peuplees.geojson
  grille_200m_non_peuplees.geojson
  isochrones_walking_15min.geojson
)

if [[ -n "${DATA_SRC:-}" ]]; then
  echo "Copie depuis $DATA_SRC"
  cp "$DATA_SRC"/*.geojson "$DATA_SRC"/*.csv data/raw/
elif [[ -n "${DATA_URL:-}" ]]; then
  echo "Téléchargement depuis $DATA_URL"
  curl -fsSL "$DATA_URL" -o /tmp/gosp_data.zip
  unzip -oq /tmp/gosp_data.zip -d data/raw
  rm -f /tmp/gosp_data.zip
else
  echo "Définir DATA_SRC (dossier local) ou DATA_URL (archive zip)." >&2
  exit 1
fi

manquants=0
for f in "${REQUIS[@]}"; do
  if [[ ! -f "data/raw/$f" ]]; then
    echo "  manquant : $f" >&2
    manquants=1
  fi
done
[[ $manquants -eq 0 ]] || { echo "Fichiers sources incomplets." >&2; exit 1; }

echo "OK — $(ls data/raw | wc -l) fichiers dans data/raw/."
echo "Étape suivante : python -m etl.build"
