#!/usr/bin/env bash
set -euo pipefail

APP_NAME="tak-pref-configurator"
APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
APP_PORT="${APP_PORT:-8080}"

log() {
  printf '[install] %s\n' "$*"
}

require_root_for_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log "Docker not found. Installing Docker..."
    if [[ "${EUID}" -ne 0 ]]; then
      log "Re-run with sudo to install Docker, or install Docker manually first."
      exit 1
    fi
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
  fi
}

ensure_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
  else
    log "Docker Compose plugin not found. Install docker-compose-plugin and retry."
    exit 1
  fi
}

write_env_file() {
  if [[ ! -f "${APP_DIR}/.env" ]]; then
    cat > "${APP_DIR}/.env" <<EOF
APP_PORT=${APP_PORT}
EOF
    log "Created ${APP_DIR}/.env"
  fi
}

main() {
  cd "${APP_DIR}"
  log "Installing ${APP_NAME} from ${APP_DIR}"
  require_root_for_docker
  ensure_compose
  write_env_file

  APP_PORT="${APP_PORT}" ${COMPOSE} -f docker-compose.yml up -d --build

  if [[ -x "${APP_DIR}/deploy/setup-nginx.sh" ]]; then
    APP_DIR="${APP_DIR}" APP_PORT="${APP_PORT}" PREF_DOMAIN="${PREF_DOMAIN:-pref.tak-solutions.com}" \
      CERTBOT_EMAIL="${CERTBOT_EMAIL:-}" bash "${APP_DIR}/deploy/setup-nginx.sh"
  fi

  log "Installation complete."
  log "Application URL: http://${PREF_DOMAIN:-pref.tak-solutions.com}/"
  log "Local URL: http://127.0.0.1:${APP_PORT}"
}

main "$@"
