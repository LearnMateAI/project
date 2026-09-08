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

Deployment uses AWS Systems Manager (SSM) instead of SSH. The workflow in `.github/workflows/deploy.yml` runs on pushes to `deployment` and can also be started manually from the Actions tab.

### One-time AWS setup

1. Attach an IAM instance profile to the EC2 instance with the `AmazonSSMManagedInstanceCore` policy so the SSM agent can receive commands.
2. Create an IAM user or role for GitHub Actions with:
   - `ssm:SendCommand`
   - `ssm:GetCommandInvocation`
   - `ssm:ListCommandInvocations`
   on the EC2 instance.
3. Ensure the EC2 instance has Docker, Git, and the SSM agent installed and running.

### Repository secrets

Configure these GitHub repository secrets:

- `AWS_ACCESS_KEY_ID`: IAM access key for the CI deploy user
- `AWS_SECRET_ACCESS_KEY`: matching secret key
- `AWS_REGION`: AWS region of the EC2 instance, for example `ap-southeast-1`
- `EC2_INSTANCE_ID`: target instance ID, for example `i-0123456789abcdef0`
- `EC2_APP_DIR`: app directory on the instance, usually `/home/ubuntu/app`
- `APP_ENV_FILE_B64`: base64-encoded production `.env` file

Optional:

- `GIT_DEPLOY_TOKEN`: GitHub fine-grained or classic token with read access to this repository, required if the repo is private and the EC2 instance cannot fetch code anonymously

Create the base64 secret from your production `.env`:

```bash
base64 -w 0 .env
```

On macOS, use `base64 .env | tr -d '\n'`.

### What the workflow does

1. Runs CI checks: Python syntax, frontend lint/build, and `docker compose config`.
2. Sends an SSM `AWS-RunShellScript` command to the EC2 instance.
3. On the instance, fetches the latest `deployment` branch and runs `scripts/deploy-ec2.sh`.
4. Writes `.env` from `APP_ENV_FILE_B64`, rebuilds containers, configures Keycloak for `PUBLIC_ORIGIN`, and verifies `/api/health`.

To deploy, push to the `deployment` branch or run **Deploy Application** manually from GitHub Actions.
