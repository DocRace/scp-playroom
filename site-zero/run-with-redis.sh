#!/usr/bin/env bash
# Start Redis Stack (OrbStack / Docker) and run Site-Zero with config defaults.
# World DB is reset each run unless you pass --no-reset-state.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start OrbStack (or Docker Desktop), then retry." >&2
  exit 1
fi

docker compose up -d

echo "Waiting for Redis..."
for _ in $(seq 1 40); do
  if docker exec site-zero-redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "Redis is up."
    break
  fi
  sleep 0.25
done

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

exec "$PY" -m site_zero "$@"
