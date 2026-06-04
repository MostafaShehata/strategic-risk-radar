$ErrorActionPreference = "Stop"
docker compose build news-ingestion data-studio-backend data-studio-frontend
docker compose run --rm --no-deps news-ingestion python -m pytest -q
