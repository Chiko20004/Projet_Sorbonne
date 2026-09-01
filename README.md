# Proximités du quotidien à Sète

Site d'analyse des proximités urbaines à Sète, dans le cadre du Global
Observatory of Sustainable Proximities (Chaire ETI — IAE Paris-Sorbonne,
UN-Habitat, UCLG). Il présente la méthodologie HQSL, le score HQVS et une
carte interactive : rosace des six fonctions sociales, radar, choroplèthe par
carreau ou par quartier, isochrones.

Stack : Flask, HTMX, Leaflet, SVG généré côté serveur. Aucun framework front.

## Installation

Prérequis : Python 3.12, GDAL (`ogr2ogr` dans le `PATH` ; sur macOS
`brew install gdal`).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Données

Les fichiers sources (~140 Mo) ne sont pas versionnés. Les placer dans
`data/raw/`, puis construire les données dérivées :

```bash
DATA_SRC=/chemin/vers/les/fichiers ./scripts/fetch_data.sh
python -m etl.build
```

L'ETL nettoie et harmonise les sources, rattache les cellules de grille aux
quartiers, et convertit les isochrones (122 Mo) en GeoPackage indexé dans
`data/processed/`. Environ dix secondes. Voir `data/README.md`.

## Lancer le site

```bash
python app.py
```

http://127.0.0.1:5000. Le rechargement automatique de Flask couvre le code
Python, pas `data/processed/` : relancer le serveur après un nouvel ETL.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `GOSP_RAW_DATA_DIR` | `data/raw/` | Fichiers sources |
| `GOSP_PROCESSED_DATA_DIR` | `data/processed/` | Sortie de l'ETL |
| `GOSP_SECRET_KEY` | clé de développement | Clé Flask, à définir en production |
| `GOSP_ISOCHRONE_SIMPLIFY_TOLERANCE` | `0.00005` | Simplification des isochrones (~5 m) |
| `PORT` | `5000` | Port du serveur de développement |

## Tests

```bash
python -m pytest tests/ -v
```

Couvre la réparation d'encodage, les formules de score, et l'ensemble des
pages et endpoints API. Les cas d'interaction visuelle sont décrits dans
`tests/CAS_DE_TEST.md` et se rejouent à la main.

## Déploiement

Application WSGI standard.

```bash
pip install -r requirements.txt
python -m etl.build
export GOSP_SECRET_KEY="<clé aléatoire longue>"
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

Placer un reverse proxy devant gunicorn pour le TLS et servir `/static/`
directement depuis le disque. `data/processed/` doit être présent sur le
serveur : il n'est pas versionné.

## Architecture

```
config.py     Constantes partagées : fonctions, modes, seuils, axes SVG
app.py        Point d'entrée WSGI
etl/          Chargement, nettoyage, agrégation spatiale, build isochrones
gosp/
  routes/     pages, exploration, quartiers, api
  services/   data_store (accès), scoring (formules), presentation (couleurs)
  templates/  layout, pages, fragments htmx, macros SVG (rosace, radar)
  static/     css (tokens, layout, composants), js (Leaflet, rosace)
scripts/      Récupération des données sources
tests/        pytest — ETL et routes
docs/         Guide utilisateur
```

## Choix de conception

Les décisions prises faute de données complètes — score pondéré, choix de
l'unité spatiale, limites des isochrones disponibles, pondération par rareté
non implémentée — sont documentées sur la page `/methodologie` du site, qui
fait référence.
