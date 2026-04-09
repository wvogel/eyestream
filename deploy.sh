#!/usr/bin/env bash
set -euo pipefail

cd "$DEPLOY_PATH"
git fetch origin main
git reset --hard origin/main
docker compose down
docker compose build --no-cache
docker compose up -d
