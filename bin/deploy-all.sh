#!/usr/bin/env sh
set -eu
docker compose up -d model
docker compose up -d db
docker compose run --rm db-migrate
docker compose up -d data-studio-backend data-studio-frontend
docker compose up -d --no-deps --force-recreate news-ingestion
docker compose ps
