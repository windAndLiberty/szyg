#!/usr/bin/env sh
set -eu
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 18080 --proxy-headers --forwarded-allow-ips='*'
