#!/usr/bin/env sh
set -eu

IMAGE_NAME="${1:-strategic-risk-radar-firecrawler:local}"
docker build -t "$IMAGE_NAME" .
