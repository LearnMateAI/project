#!/usr/bin/env sh
# Point the learnmate-frontend client at this server's public origin, and switch off the
# realm's well-known dev/dev account. Run by scripts/deploy-ec2.sh after every deploy.
#
# The realm JSON only lists localhost redirect URIs, and --import-realm never touches a
# realm that already exists, so the public origin has to be set through the admin API.
set -eu

: "${PUBLIC_ORIGIN:?PUBLIC_ORIGIN must be set}"
: "${KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD must be set}"

compose="${COMPOSE_CMD:-docker compose}"
keycloak_server="http://localhost:8080/auth"

kcadm() {
  $compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

first_id() {
  sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
}

# The admin user is only bootstrapped once Keycloak has finished starting, a little after
# its port opens.
logged_in=0
for _ in $(seq 1 60); do
  if kcadm config credentials --server "$keycloak_server" --realm master \
       --user admin --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null 2>&1; then
    logged_in=1
    break
  fi
  sleep 3
done
if [ "$logged_in" -ne 1 ]; then
  echo "Could not log in to Keycloak's admin API" >&2
  exit 1
fi

client_id=$(kcadm get clients -r learnmate -q clientId=learnmate-frontend --fields id | first_id)
if [ -z "$client_id" ]; then
  echo "learnmate-frontend client was not found" >&2
  exit 1
fi

kcadm update "clients/$client_id" -r learnmate \
  -s "redirectUris=[\"${PUBLIC_ORIGIN}/*\"]" \
  -s "webOrigins=[\"${PUBLIC_ORIGIN}\"]"
echo "Keycloak client configured for $PUBLIC_ORIGIN"

# dev/dev is in the realm file for local development. On a public server it is a login
# anyone who has read the repo can use. KEEP_DEV_USER=1 in .env leaves it enabled.
if [ "${KEEP_DEV_USER:-0}" != "1" ]; then
  dev_id=$(kcadm get users -r learnmate -q username=dev -q exact=true --fields id | first_id)
  if [ -n "$dev_id" ]; then
    kcadm update "users/$dev_id" -r learnmate -s enabled=false
    echo "Disabled the dev user"
  fi
fi
