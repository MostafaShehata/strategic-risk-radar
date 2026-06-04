$ErrorActionPreference = "Stop"
docker compose up -d db
docker compose run --rm db-migrate
docker compose up -d data-studio-backend data-studio-frontend
docker compose run --rm news-ingestion
docker compose ps
