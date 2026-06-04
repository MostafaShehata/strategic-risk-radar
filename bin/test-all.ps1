$ErrorActionPreference = "Stop"
docker compose build ingestion
docker compose run --rm --no-deps ingestion python -m pytest -q

