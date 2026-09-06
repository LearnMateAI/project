#!/usr/bin/env sh
set -eu

: "${PUBLIC_ORIGIN:?PUBLIC_ORIGIN must be set}"
: "${KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD must be set}"

compose="${COMPOSE_CMD:-docker compose}"
keycloak_server="http://localhost:8080/auth"

$compose exec -T keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$keycloak_server" \
  --realm master \
  --user admin \
  --password "$KEYCLOAK_ADMIN_PASSWORD"

client_id=$($compose exec -T keycloak /opt/keycloak/bin/kcadm.sh get clients \
  -r learnmate -q clientId=learnmate-frontend --fields id \
  | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)

if [ -z "$client_id" ]; then
  echo "learnmate-frontend client was not found" >&2
  exit 1
fi

redirect_uris="[\"${PUBLIC_ORIGIN}/*\"]"
web_origins="[\"${PUBLIC_ORIGIN}\"]"

$compose exec -T keycloak /opt/keycloak/bin/kcadm.sh update "clients/$client_id" \
  -r learnmate \
  -s "redirectUris=$redirect_uris" \
  -s "webOrigins=$web_origins"

echo "Keycloak client configured for $PUBLIC_ORIGIN"
