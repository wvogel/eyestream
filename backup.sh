#!/bin/bash
set -euo pipefail

# cd to the directory where this script lives (= project root)
cd "$(dirname "$(readlink -f "$0")")"

# Load DB credentials from .env
if [ -f .env ]; then
  export $(grep -E '^DB_(NAME|USER)=' .env | xargs)
fi

backup_name=$(date +'%Y-%m-%d')
backup_dir=./backup

mkdir -p "${backup_dir}"
docker compose exec -T postgres pg_dumpall -U "${DB_USER:-eyestream}" | gzip > "${backup_dir}/${backup_name}.gz"

# Keep only the 3 most recent backups
cd "${backup_dir}"
ls -1t *.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
