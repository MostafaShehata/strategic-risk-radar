#!/usr/bin/env sh
set -eu
docker compose -f ../docker-compose.yml up -d db
docker compose -f ../docker-compose.yml run --rm db-migrate
