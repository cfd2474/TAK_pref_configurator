#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DOMAIN="${PREF_DOMAIN:-pref.tak-solutions.com}"
APP_PORT="${APP_PORT:-8080}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

log() {
  printf '[nginx] %s\n' "$*"
}

if [[ "${EUID}" -ne 0 ]]; then
  log "Run as root (or with sudo)."
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  log "Installing nginx..."
  apt-get update -qq
  apt-get install -y -qq nginx
  systemctl enable nginx
fi

SITE_AVAILABLE="/etc/nginx/sites-available/${DOMAIN}.conf"
SITE_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}.conf"
SOURCE_CONF="${APP_DIR}/deploy/nginx/pref.tak-solutions.com.conf"

if [[ ! -f "${SOURCE_CONF}" ]]; then
  log "Missing nginx config: ${SOURCE_CONF}"
  exit 1
fi

log "Installing nginx site for ${DOMAIN} -> 127.0.0.1:${APP_PORT}"
cp "${SOURCE_CONF}" "${SITE_AVAILABLE}"
ln -sf "${SITE_AVAILABLE}" "${SITE_ENABLED}"

if [[ -f /etc/nginx/sites-enabled/default ]]; then
  rm -f /etc/nginx/sites-enabled/default
fi

nginx -t
systemctl reload nginx

if [[ -n "${CERTBOT_EMAIL}" ]] && ! grep -q "listen 443" "${SITE_AVAILABLE}" 2>/dev/null; then
  if ! command -v certbot >/dev/null 2>&1; then
    log "Installing certbot..."
    apt-get install -y -qq certbot python3-certbot-nginx
  fi
  log "Requesting TLS certificate for ${DOMAIN}..."
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect || \
    log "Certbot failed; site remains available on http://${DOMAIN}/"
fi

log "Nginx configured for http://${DOMAIN}/"
