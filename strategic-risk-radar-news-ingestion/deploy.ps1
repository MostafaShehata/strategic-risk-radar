$ErrorActionPreference = "Stop"
docker compose -f ..\docker-compose.yml up --no-deps --force-recreate news-ingestion
