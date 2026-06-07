$ErrorActionPreference = "Stop"
docker compose up -d model
docker compose up -d vector-db
docker compose up -d rag-api
docker compose up -d firecrawler
docker compose up -d db
docker compose run --rm db-migrate
docker compose up -d data-studio-backend data-studio-frontend
docker compose up -d --no-deps --force-recreate news-ingestion
docker compose up -d --no-deps --force-recreate news-enrichment
docker compose ps
