# AWS Deployment Guide

## Architecture

```
GitHub push -> GitHub Actions CI -> AWS SSM -> EC2 (docker compose) -> Nginx -> Browser
```

- **EC2**: Ubuntu, Docker, Git, SSM Agent
- **Compose**: Nginx (80/443) → Frontend + Backend + Keycloak, MongoDB, Qdrant (internal only)
- **CI/CD**: GitHub Actions runs tests, then deploys via AWS Systems Manager (no SSH needed)
- **Domain**: `learnmateai.dinurag.dev` with Let's Encrypt certs on Nginx

---

## 1. One-time EC2 Setup

### 1.1 Launch Instance

```bash
# Recommended: Ubuntu 22.04 LTS
# Instance type: t3.large or larger (needs RAM for two ~2GB GGUF models)
# Storage: 30GB+ GP3 (models + vector data + MongoDB)
# Security group: allow inbound TCP 22 (SSH), 80, 443 from 0.0.0.0/0
#                everything else is internal-only
```

### 1.2 SSH and Bootstrap

```bash
ssh ubuntu@<EC2_PUBLIC_IP>

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu

# Install Git
sudo apt update && sudo apt install -y git

# Verify SSM Agent (preinstalled on Ubuntu AMIs)
sudo systemctl status snap.amazon-ssm-agent.amazon-ssm-agent.service
# If not running: sudo snap install amazon-ssm-agent --classic
```

### 1.3 Attach IAM Instance Profile

1. Go to AWS Console → IAM → Roles → **Create role**
2. Trusted entity: **AWS service** → **EC2**
3. Attach policy: `AmazonSSMManagedInstanceCore`
4. Name it e.g. `LearnMateEC2SSM`
5. EC2 Console → Instances → select your instance → **Actions → Security → Modify IAM role**
6. Attach the `LearnMateEC2SSM` role

Verify from your local machine:

```bash
aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=<EC2_INSTANCE_ID>" \
  --query "InstanceInformationList[].InstanceId" \
  --output text
# Should return your instance ID
```

### 1.4 Create CI IAM User for GitHub Actions

1. IAM → Users → **Add user** → name: `LearnMateCICD`
2. Access type: **Programmatic access**
3. Attach policy: **Create inline policy** (JSON):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand",
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations",
        "ssm:DescribeInstanceInformation"
      ],
      "Resource": [
        "arn:aws:ec2:<REGION>:<ACCOUNT_ID>:instance/<EC2_INSTANCE_ID>",
        "arn:aws:ssm:<REGION>:<ACCOUNT_ID>:managed-instance/*"
      ]
    }
  ]
}
```

4. Save the **Access Key ID** and **Secret Access Key**

---

## 2. GitHub Repository Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value | Required |
|--------|-------|----------|
| `AWS_ACCESS_KEY_ID` | CI IAM user access key | Yes |
| `AWS_SECRET_ACCESS_KEY` | CI IAM user secret key | Yes |
| `AWS_REGION` | e.g. `ap-southeast-1` | Yes |
| `EC2_INSTANCE_ID` | e.g. `i-0123456789abcdef0` | Yes |
| `EC2_APP_DIR` | e.g. `/home/ubuntu/app` | Yes |
| `APP_ENV_FILE_B64` | base64-encoded `.env` (see below) | Yes (first deploy) |
| `GIT_DEPLOY_TOKEN` | GitHub PAT with repo read access | If repo is private |

### Generate `APP_ENV_FILE_B64`

```bash
cd ~/app  # your local project root
base64 -w 0 .env
# On macOS: base64 .env | tr -d '\n'
```

Copy the output string and paste it as the `APP_ENV_FILE_B64` secret value.

---

## 3. Deploy

### Option A: Automatic (push to `deployment` branch)

```bash
git checkout deployment
git merge main   # or whatever branch has your changes
git push origin deployment
```

GitHub Actions will:
1. Run Python syntax check
2. Run frontend lint + build
3. Validate `docker compose config`
4. Send SSM deploy command to EC2
5. EC2 pulls code, builds containers, configures Keycloak, verifies health

### Option B: Manual trigger

GitHub Console → Actions → **Deploy Application** → **Run workflow** → branch: `deployment`

---

## 4. Post-Deploy Verification

```bash
# Check health
curl https://learnmateai.dinurag.dev/api/health

# Check containers (via SSM)
aws ssm send-command \
  --instance-ids <EC2_INSTANCE_ID> \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["docker compose -f /home/ubuntu/app/docker-compose.yml ps"]'
```

---

## 5. Subsequent Updates

Just push to the `deployment` branch. The workflow handles everything.

**Do not run `docker compose down -v`** — that deletes MongoDB, Qdrant, Keycloak, and model volumes.

---

## 6. Troubleshooting

| Issue | Fix |
|-------|-----|
| SSM "instance not online" | Check IAM role, SSM agent status, security group allows outbound HTTPS |
| Keycloak redirect mismatch | `configure-keycloak.sh` runs after deploy; verify `PUBLIC_ORIGIN` matches domain |
| Models downloading slowly | First request downloads ~4GB GGUF files; subsequent requests use cached volume |
| Nginx 502 | Backend still starting; wait 60s and retry; check `docker compose ps` |
| OOM kills | Instance too small; upgrade to t3.xlarge or add swap |

---

## 7. Local Testing Before Push

```bash
# Validate compose config
docker compose config

# Full stack
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1/api/health

# Keycloak setup
PUBLIC_ORIGIN="https://learnmateai.dinurag.dev" \
  KEYCLOAK_ADMIN_PASSWORD="<your-password>" \
  ./scripts/configure-keycloak.sh
```
