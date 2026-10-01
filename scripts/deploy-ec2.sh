#!/usr/bin/env bash
# Bring the stack up on the EC2 host from the current checkout.
#
# Run by the SSM bootstrap (scripts/build-ssm-deploy-params.py) from the app directory
# after it has checked out the deploy branch. Safe to run by hand there too:
#
#     cd ~/app && ./scripts/deploy-ec2.sh
#
# Idempotent: every step either checks first or is safe to repeat, so a failed deploy is
# fixed by pushing a fix and deploying again.
set -euo pipefail

cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"

# --- .env ---------------------------------------------------------------------------------
if [ -n "${APP_ENV_FILE_B64:-}" ]; then
  # tr: a .env saved on Windows carries CRLFs, which would end up inside every value.
  echo "$APP_ENV_FILE_B64" | base64 -d | tr -d '\r' > .env
  chmod 600 .env
elif [ ! -f .env ]; then
  echo "Missing .env and APP_ENV_FILE_B64 was not provided" >&2
  exit 1
fi
set -a
. ./.env
set +a
: "${PUBLIC_HOST:?PUBLIC_HOST must be set in .env}"
: "${PUBLIC_ORIGIN:?PUBLIC_ORIGIN must be set in .env}"
: "${KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD must be set in .env}"
: "${JWT_SECRET_KEY:?JWT_SECRET_KEY must be set in .env}"

# --- Docker access ------------------------------------------------------------------------
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
export COMPOSE_CMD DOCKER_CMD

# --- Swap ---------------------------------------------------------------------------------
# Headroom for the llama-cpp-python compile and the first load of both models together.
if [ "$(swapon --show | wc -l)" -eq 0 ]; then
  echo "No swap detected. Adding 4G swap file to prevent OOM kills..."
  sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-learnmate-swap.conf >/dev/null
  sudo sysctl -q -p /etc/sysctl.d/99-learnmate-swap.conf || true
fi

# --- TLS certificate ------------------------------------------------------------------------
# Nginx will not start without one, so issue it before the stack comes up. certbot's
# standalone mode needs port 80, which our own Nginx holds once it is running -- hence the
# stop here, and the renewal hooks below that do the same around every automatic renewal.
CERT_FILE="/etc/letsencrypt/live/${PUBLIC_HOST}/fullchain.pem"
if ! command -v certbot >/dev/null 2>&1; then
  echo "Installing certbot..."
  sudo snap install --classic certbot
  sudo ln -sf /snap/bin/certbot /usr/bin/certbot
fi
if ! sudo test -f "$CERT_FILE"; then
  echo "No certificate for ${PUBLIC_HOST}; requesting one from Let's Encrypt..."
  $COMPOSE_CMD stop nginx >/dev/null 2>&1 || true
  if [ -n "${CERTBOT_EMAIL:-}" ]; then
    email_args=(-m "$CERTBOT_EMAIL")
  else
    email_args=(--register-unsafely-without-email)
  fi
  if ! sudo certbot certonly --standalone --non-interactive --agree-tos "${email_args[@]}" \
       -d "$PUBLIC_HOST"; then
    echo "certbot failed. Check that the DNS A record for ${PUBLIC_HOST} points at this" >&2
    echo "instance's public IP and that port 80 is open in its security group." >&2
    exit 1
  fi
fi
sudo mkdir -p /etc/letsencrypt/renewal-hooks/pre /etc/letsencrypt/renewal-hooks/post
printf '#!/bin/sh\ncd %s && docker compose stop nginx\n' "$APP_DIR" \
  | sudo tee /etc/letsencrypt/renewal-hooks/pre/learnmate-stop-nginx.sh >/dev/null
printf '#!/bin/sh\ncd %s && docker compose start nginx\n' "$APP_DIR" \
  | sudo tee /etc/letsencrypt/renewal-hooks/post/learnmate-start-nginx.sh >/dev/null
sudo chmod +x /etc/letsencrypt/renewal-hooks/pre/learnmate-stop-nginx.sh \
              /etc/letsencrypt/renewal-hooks/post/learnmate-start-nginx.sh

# --- Build and start ----------------------------------------------------------------------
echo "=== Building and starting containers ==="
$COMPOSE_CMD up -d --build --remove-orphans

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
    # "running" is only ever reported for a container without a healthcheck.
    if [ "$health" = "healthy" ] || [ "$health" = "running" ]; then
      echo "$service is $health"
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo "$service did not become healthy within ${timeout}s" >&2
  $COMPOSE_CMD logs --tail 100 "$service" || true
  return 1
}

wait_for_keycloak() {
  local timeout="${1:-300}"
  local elapsed=0
  echo "Waiting for Keycloak to accept connections (up to ${timeout}s)..."
  while [ "$elapsed" -lt "$timeout" ]; do
    if $COMPOSE_CMD exec -T keycloak bash -c 'exec 3<> /dev/tcp/127.0.0.1/8080' >/dev/null 2>&1; then
      echo "Keycloak is up"
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo "Keycloak did not come up within ${timeout}s" >&2
  $COMPOSE_CMD logs --tail 100 keycloak || true
  return 1
}

if ! wait_for_container_healthy mongo 180; then
  free -h || true
  df -h / || true
  exit 1
fi
wait_for_container_healthy qdrant 120
wait_for_keycloak 300

./scripts/configure-keycloak.sh

wait_for_container_healthy backend 600
wait_for_container_healthy frontend 120

# Through Nginx and TLS, the way a browser gets there.
echo "Checking https://${PUBLIC_HOST}/api/health through Nginx..."
ok=0
for _ in $(seq 1 24); do
  if curl -fsS --resolve "${PUBLIC_HOST}:443:127.0.0.1" "https://${PUBLIC_HOST}/api/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 5
done
if [ "$ok" -ne 1 ]; then
  echo "Health check through Nginx failed" >&2
  $COMPOSE_CMD logs --tail 100 nginx || true
  exit 1
fi

# Old image layers from previous builds; the disk is not large.
$DOCKER_CMD image prune -f >/dev/null 2>&1 || true

echo "=== Deployment complete: ${PUBLIC_ORIGIN} ==="
$COMPOSE_CMD ps
