# AWS deployment

The repository root is the deployment entrypoint. It runs the frontend, Nginx, FastAPI backend, Keycloak, MongoDB and Qdrant with one Compose project.

## One-time EC2 setup

Use an Ubuntu EC2 instance with enough disk and memory for two local GGUF models. A small instance will start the web stack but may not have enough memory for chat and resource generation.

Install Docker and Git, then clone this repository as the deployment user:

```bash
git clone <repository-url> ~/app
cd ~/app
cp .env.example .env
chmod 600 .env
```

Edit `.env`:

```dotenv
PUBLIC_HOST=your-domain.example.com
PUBLIC_ORIGIN=https://your-domain.example.com
JWT_SECRET_KEY=<random-32-byte-secret>
KEYCLOAK_ADMIN_PASSWORD=<strong-password>
```

A fixed Elastic IP is recommended for a direct EC2 deployment. Point DNS at that address. Allow inbound TCP `80` and `443` in the security group; keep MongoDB, Qdrant, Keycloak and port `8000` private.

For a first HTTP-only smoke test, use `PUBLIC_ORIGIN=http://<elastic-ip>`. Put HTTPS in front of the stack before real users access it, preferably with an AWS Application Load Balancer and ACM certificate, or terminate TLS in Nginx and update `PUBLIC_ORIGIN` to `https://...`.

## Start and update

```bash
cd ~/app
docker compose up -d --build
docker compose ps
PUBLIC_ORIGIN="$(grep '^PUBLIC_ORIGIN=' .env | cut -d= -f2-)" \
  KEYCLOAK_ADMIN_PASSWORD="$(grep '^KEYCLOAK_ADMIN_PASSWORD=' .env | cut -d= -f2-)" \
  ./scripts/configure-keycloak.sh
curl -fsS http://127.0.0.1/api/health
```

The first model request may download the configured GGUF files. They are stored in the `model_data` volume and survive container rebuilds. MongoDB, Qdrant and Keycloak data also use named volumes and survive normal updates.

For later releases:

```bash
git fetch origin
git checkout deployment
git reset --hard origin/deployment
docker compose up -d --build --remove-orphans
PUBLIC_ORIGIN="$(grep '^PUBLIC_ORIGIN=' .env | cut -d= -f2-)" \
  KEYCLOAK_ADMIN_PASSWORD="$(grep '^KEYCLOAK_ADMIN_PASSWORD=' .env | cut -d= -f2-)" \
  ./scripts/configure-keycloak.sh
curl -fsS http://127.0.0.1/api/health
```

Do not run `docker compose down -v` during an application update. The `-v` flag deletes the database, vector, Keycloak and model volumes.

## GitHub Actions CI/CD

Configure these repository secrets:

- `EC2_HOST`: Elastic IP or DNS name
- `EC2_USERNAME`: SSH user, usually `ubuntu`
- `EC2_SSH_KEY`: private key for that user

The workflow in `.github/workflows/deploy.yml` runs on pushes to `deployment` and can also be started manually. The EC2 user must be able to run Docker, and `~/app/.env` must already contain the production secrets. CI never writes secrets into Git.

The workflow builds and tests the frontend, validates the Compose file, updates the checkout, rebuilds changed images, configures the Keycloak client for `PUBLIC_ORIGIN`, and waits for `/api/health`.
