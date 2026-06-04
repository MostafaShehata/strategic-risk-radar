#!/usr/bin/env sh
set -eu
docker compose -f ../docker-compose.yml up -d --no-deps --force-recreate news-ingestion
