#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAILY="$BACKUP_DIR/daily/szyg-control-$STAMP.dump"
docker compose -f "$ROOT/docker-compose.yml" exec -T postgres \
  pg_dump -U szyg -d szyg_control -Fc > "$DAILY"
if [ "$(date -u +%u)" = "7" ]; then
  cp "$DAILY" "$BACKUP_DIR/weekly/szyg-control-$STAMP.dump"
fi
find "$BACKUP_DIR/daily" -type f -name 'szyg-control-*.dump' -mtime +7 -delete
find "$BACKUP_DIR/weekly" -type f -name 'szyg-control-*.dump' -mtime +28 -delete
