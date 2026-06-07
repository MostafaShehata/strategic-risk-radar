$ErrorActionPreference = "Stop"
docker compose -f ..\docker-compose.yml up -d postgres-db
docker compose -f ..\docker-compose.yml run --rm db-migrate
