# AWS deployment

The supported deployment target is one Ubuntu 22.04 EC2 instance running Docker Compose.
Nginx exposes the complete application on port 80; MongoDB, Qdrant, Keycloak, the API, and
the frontend remain on the private Compose network.

## EC2 preparation

Use an instance with at least 8 GB RAM and enough EBS for the model files and MongoDB data.
The AWS free tier can cover a small eligible instance, but this workload is CPU and memory
heavy; model generation may be slow and storage or data-transfer charges can still apply.

Install Docker and clone this repository on the instance at `/home/ubuntu/learnmate` (or set
the `EC2_APP_DIR` GitHub secret). Open inbound TCP port 80 in the security group. Do not
expose 27017, 6333, 8080, or 8000 publicly.

## GitHub secrets

Add these repository secrets:

- `EC2_HOST`: public IPv4 address or DNS name
- `EC2_USERNAME`: usually `ubuntu` for Ubuntu AMIs
- `EC2_SSH_KEY`: private key for the instance
- `APP_ENV_FILE_B64`: base64-encoded production `.env` file
- `EC2_APP_DIR`: optional absolute path; defaults to `/home/<EC2_USERNAME>/learnmate`

Create the environment secret locally without committing it:

```bash
base64 -w 0 .env > app-env.b64
```

The deployed `.env` must contain a random `JWT_SECRET_KEY`, the EC2 public URL as both
`FRONTEND_ORIGIN` and the host portion of `KEYCLOAK_ISSUER`, and the private JWKS URL:

```dotenv
FRONTEND_ORIGIN=http://YOUR_EC2_PUBLIC_DNS
KEYCLOAK_ENABLED=true
KEYCLOAK_ISSUER=http://YOUR_EC2_PUBLIC_DNS/auth/realms/learnmate
KEYCLOAK_JWKS_URL=http://keycloak:8080/auth/realms/learnmate/protocol/openid-connect/certs
LEARNMATE_MONGODB_URI=mongodb://mongo:27017
LEARNMATE_QDRANT_URL=http://qdrant:6333
```

The Keycloak realm file also contains browser redirect origins. Replace its example domain
with the EC2 public URL before deployment, or use a domain name and HTTPS reverse proxy for
production. The frontend continues to use `/api` and `/auth`, so no frontend rebuild-time
host changes are needed.

Every push to `main`, `master`, or `dinura-deployment` runs the 15-case CI gate, frontend
lint/build, and Compose validation. A successful push then deploys the full stack and polls
`/api/health` before succeeding.
