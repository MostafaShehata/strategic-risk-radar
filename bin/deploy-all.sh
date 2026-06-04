#!/usr/bin/env sh
set -eu
docker compose up -d db data-studio
docker compose run --rm ingestion
docker compose ps

