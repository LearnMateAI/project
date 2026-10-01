# AWS Deployment

```
push to `production` → GitHub Actions (build checks) → AWS SSM → EC2: docker compose → Nginx (443) → browser
```

- **EC2**: Ubuntu 22.04, t3.xlarge (16 GB), 40 GB gp3, Elastic IP, role `LearnMateEC2SSM`
- **Stack** (`docker-compose.yml`): Nginx on 80/443 in front of frontend, backend (`/api`) and
  Keycloak (`/auth`); MongoDB and Qdrant are internal only
- **Site**: https://learnmateai.dinurag.dev, Let's Encrypt certificate on the host
- **No SSH in the pipeline**: GitHub Actions sends the deploy as an SSM command

## One-time AWS setup

1. **IAM role for the instance**: IAM → Roles → Create role → AWS service / EC2 →
   `AmazonSSMManagedInstanceCore` → name `LearnMateEC2SSM`.
2. **Instance**: Ubuntu 22.04, t3.xlarge, 40 GiB gp3, security group allowing 22 (My IP),
   80 and 443 (anywhere), IAM instance profile `LearnMateEC2SSM`.
3. **Elastic IP**: allocate and associate it with the instance.
4. **DNS**: `A learnmateai.dinurag.dev → <Elastic IP>` (DNS only, not proxied).
5. **CI user**: IAM user `LearnMateCICD` with this inline policy, then an access key:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ec2:<REGION>:<ACCOUNT_ID>:instance/<INSTANCE_ID>",
        "arn:aws:ssm:<REGION>::document/AWS-RunShellScript"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:DescribeInstanceInformation"],
      "Resource": "*"
    }
  ]
}
```

Docker, Git, certbot, swap and the TLS certificate are all set up by the first deploy, so
the instance needs nothing installed by hand.

## GitHub secrets

Settings → Environments → `production` → Environment secrets:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | the CI user's access key |
| `AWS_REGION` | e.g. `eu-north-1` |
| `EC2_INSTANCE_ID` | `i-…` |
| `EC2_APP_DIR` | `/home/ubuntu/app` |
| `APP_ENV_FILE_B64` | the server's `.env` (from `.env.example`), base64-encoded |
| `GIT_DEPLOY_TOKEN` | read-only GitHub token; only if the repo is private |

Encode the `.env` with `base64 -w 0 .env`, or in PowerShell:
`[Convert]::ToBase64String([IO.File]::ReadAllBytes(".env"))`.

## Deploying

Push to `production`, or Actions → **Deploy Application** → Run workflow on `production`.

The first deploy is the slow one: it compiles llama.cpp into the backend image, and the
backend then downloads both GGUFs (~4 GB) into the `model_data` volume in the background.
Later deploys reuse the Docker layer cache and the volume.

On the instance, `scripts/deploy-ec2.sh` writes `.env`, issues the certificate if there is
none, runs `docker compose up -d --build`, waits for each service, points the Keycloak
client at `PUBLIC_ORIGIN` (`scripts/configure-keycloak.sh`), disables the realm's `dev`
account, and checks `/api/health` through Nginx.

**Never run `docker compose down -v` on the server.** It deletes the uploaded documents,
the vectors, every Keycloak account and the downloaded models.

## Checking on it

```bash
curl https://learnmateai.dinurag.dev/api/health
```

On the instance (SSH, or EC2 → Connect → Session Manager):

```bash
cd ~/app
docker compose ps
docker compose logs --tail 100 backend
```

Keycloak's admin console is at `/auth/admin` (user `admin`, password
`KEYCLOAK_ADMIN_PASSWORD` from the server's `.env`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| "not online in SSM" | Role `LearnMateEC2SSM` attached? Instance running? Wait a few minutes after attaching. |
| certbot fails | DNS A record must point at the Elastic IP, and port 80 must be open. |
| Login redirects to an error | `PUBLIC_ORIGIN` must exactly match the site URL; redeploy to re-run `configure-keycloak.sh`. |
| 502 from Nginx | Backend still starting; `docker compose logs backend`. |
| First answer is slow | The models are still downloading or loading; watch `docker compose logs -f backend`. |
