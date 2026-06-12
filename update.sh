#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

log() {
  printf '[update] %s\n' "$*"
}

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  log "Docker Compose not found."
  exit 1
fi

main() {
  cd "${APP_DIR}"

  if [[ -d .git ]]; then
    log "Pulling latest changes..."
    git pull --ff-only
  else
    log "No git repository found; skipping git pull."
  fi

  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi

  log "Rebuilding and restarting container..."
  ${COMPOSE} -f docker-compose.yml up -d --build

  log "Update complete."
  log "Application URL: http://127.0.0.1:${APP_PORT:-8080}"
}

main "$@"
