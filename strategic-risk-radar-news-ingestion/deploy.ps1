$ErrorActionPreference = "Stop"
docker compose -f ..\docker-compose.yml run --rm news-ingestion
