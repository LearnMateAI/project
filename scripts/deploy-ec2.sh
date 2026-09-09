#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/app}"
APP_DIR="${APP_DIR/#\~/$HOME}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-deployment}"
GITHUB_REPO="${GITHUB_REPO:-LearnMateAI/project}"

mkdir -p "$APP_DIR"
cd "$APP_DIR"

if [ ! -d .git ]; then
  git init
  git remote add origin "https://github.com/${GITHUB_REPO}.git"
fi

if [ -n "${GIT_DEPLOY_TOKEN:-}" ]; then
  git remote set-url origin "https://x-access-token:${GIT_DEPLOY_TOKEN}@github.com/${GITHUB_REPO}.git"
fi

git fetch origin "${DEPLOY_BRANCH}"
git checkout "${DEPLOY_BRANCH}" || git checkout -b "${DEPLOY_BRANCH}" "origin/${DEPLOY_BRANCH}"
git reset --hard "origin/${DEPLOY_BRANCH}"

if [ -n "${APP_ENV_FILE_B64:-}" ]; then
  echo "$APP_ENV_FILE_B64" | base64 -d | tr -d '\r' > .env
  chmod 600 .env
elif [ ! -f .env ]; then
  echo "Missing .env and APP_ENV_FILE_B64 was not provided" >&2
  exit 1
fi
set -a
. ./.env
set +a

if docker info >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
  DOCKER_CMD="docker"
elif sudo -n docker info >/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker compose"
  DOCKER_CMD="sudo docker"
else
  echo "Docker daemon is not accessible for the deployment user" >&2
  exit 1
fi
export COMPOSE_CMD
export DOCKER_CMD

if [ "$(swapon --show | wc -l)" -eq 0 ]; then
  echo "No swap detected. Adding 4G swap file to prevent OOM kills..."
  sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf >/dev/null
  echo "Swap enabled"
else
  echo "Swap already active:"
  swapon --show
fi

chmod +x ./scripts/configure-keycloak.sh

echo "=== Building and starting containers ==="
$COMPOSE_CMD up -d --build --remove-orphans --force-recreate || true

echo "=== Container status ==="
$COMPOSE_CMD ps || true

wait_for_container_healthy() {
  local service="$1"
  local timeout="${2:-300}"
  local elapsed=0
  echo "Waiting for $service to become healthy (up to ${timeout}s)..."
  while [ "$elapsed" -lt "$timeout" ]; do
    local container_id health
    container_id=$($COMPOSE_CMD ps -q "$service" 2>/dev/null | head -n 1 || true)
    health=""
    if [ -n "$container_id" ]; then
      health=$($DOCKER_CMD inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)
    fi
    if [ "$health" = "healthy" ]; then
      echo "$service is healthy"
      return 0
    fi
    if [ "$health" = "unhealthy" ]; then
      echo "$service is unhealthy, checking logs..." >&2
      $COMPOSE_CMD logs --tail 50 "$service" || true
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo "$service did not become healthy within ${timeout}s" >&2
  $COMPOSE_CMD logs --tail 100 "$service" || true
  return 1
}

wait_for_keycloak_http() {
  local timeout="${1:-300}"
  local elapsed=0
  echo "Waiting for Keycloak HTTP /auth/health/ready (up to ${timeout}s)..."
  while [ "$elapsed" -lt "$timeout" ]; do
    if $COMPOSE_CMD exec -T keycloak sh -c \
      'exec 3<> /dev/tcp/127.0.0.1/8080; echo -e "GET /auth/health/ready HTTP/1.1\r\nhost: localhost\r\nConnection: close\r\n\r\n" >&3; head -n 1 <&3 | grep -q "200 OK"' \
      >/dev/null 2>&1; then
      echo "Keycloak HTTP is ready"
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo "Keycloak HTTP did not become ready within ${timeout}s" >&2
  return 1
}

if ! wait_for_container_healthy "mongo" 180; then
  echo "Mongo failed to start. Checking system resources..." >&2
  free -h || true
  df -h / || true
  $COMPOSE_CMD logs --tail 100 mongo || true
  exit 1
fi

if ! wait_for_container_healthy "qdrant" 120; then
  echo "Qdrant failed to start" >&2
  $COMPOSE_CMD logs --tail 100 qdrant || true
  exit 1
fi

if ! wait_for_keycloak_http 180; then
  echo "Keycloak did not become ready in time" >&2
  $COMPOSE_CMD logs --tail 100 keycloak || true
  exit 1
fi

PUBLIC_ORIGIN="$PUBLIC_ORIGIN" KEYCLOAK_ADMIN_PASSWORD="$KEYCLOAK_ADMIN_PASSWORD" \
  COMPOSE_CMD="$COMPOSE_CMD" ./scripts/configure-keycloak.sh

echo "Waiting for backend to become healthy..."
for i in $(seq 1 60); do
  if curl -fsSL http://127.0.0.1/api/health >/dev/null 2>&1; then
    echo "Backend health check passed"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "Backend health check failed" >&2
    $COMPOSE_CMD logs --tail 200 backend || true
    $COMPOSE_CMD logs --tail 200 mongo || true
    exit 1
  fi
  sleep 5
done

echo "=== Deployment complete ==="
$COMPOSE_CMD ps
