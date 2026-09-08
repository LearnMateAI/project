#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/app}"
cd "$APP_DIR"

if [ -n "${APP_ENV_FILE_B64:-}" ]; then
  echo "$APP_ENV_FILE_B64" | base64 -d > .env
  chmod 600 .env
elif [ ! -f .env ]; then
  echo "Missing .env and APP_ENV_FILE_B64 was not provided" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

if docker info >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif sudo -n docker info >/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker compose"
else
  echo "Docker daemon is not accessible for the deployment user" >&2
  exit 1
fi
export COMPOSE_CMD

chmod +x ./scripts/configure-keycloak.sh

$COMPOSE_CMD up -d --build --remove-orphans

sleep 10

PUBLIC_ORIGIN="$PUBLIC_ORIGIN" KEYCLOAK_ADMIN_PASSWORD="$KEYCLOAK_ADMIN_PASSWORD" \
  COMPOSE_CMD="$COMPOSE_CMD" ./scripts/configure-keycloak.sh

$COMPOSE_CMD ps

if curl -fsS http://127.0.0.1/api/health >/dev/null; then
  echo "Backend health check passed"
else
  echo "Backend health check failed" >&2
  $COMPOSE_CMD logs --tail 200 backend || true
  exit 1
fi
