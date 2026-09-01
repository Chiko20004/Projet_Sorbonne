# Données

Deux dossiers, aucun des deux versionné.

| Dossier | Contenu | Origine |
|---|---|---|
| `data/raw/` | Fichiers sources fournis par la Chaire ETI (~140 Mo) | `scripts/fetch_data.sh` |
| `data/processed/` | Sortie de l'ETL, lue au démarrage de Flask (~85 Mo) | `python -m etl.build` |

Les sources sont un extrait allégé de la base PostgreSQL de production
(~7 Go). Millésime BPE 2024. Elles ne nous appartiennent pas et ne sont pas
redistribuées avec ce dépôt.
