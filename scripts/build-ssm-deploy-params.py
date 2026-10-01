#!/usr/bin/env python3
"""
Build the AWS SSM `send-command` parameters for one deployment.

SSM runs the result as root on the instance. That root half only does what needs root --
installing Docker and Git if the instance is fresh -- then hands over to the deploy user,
who checks out DEPLOY_BRANCH and runs scripts/deploy-ec2.sh from it. Everything that
changes between deployments therefore lives in the repo, not in this bootstrap.

The script travels base64-encoded because the AWS CLI's parameter parser mangles quotes
and newlines in an inline shell script.
"""

from __future__ import annotations

import base64
import json
import os
import sys

# AWS caps an SSM command document's parameters at 97 KB.
MAX_PARAMS_BYTES = 97000


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def main() -> int:
    app_dir = os.environ.get("EC2_APP_DIR", "").strip()
    instance_id = os.environ.get("EC2_INSTANCE_ID", "").strip()
    github_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    deploy_branch = os.environ.get("DEPLOY_BRANCH", "").strip() or "production"
    app_env_b64 = os.environ.get("APP_ENV_FILE_B64", "")
    git_token = os.environ.get("GIT_DEPLOY_TOKEN", "")

    if not app_dir or not instance_id or not github_repo:
        print("EC2_APP_DIR, EC2_INSTANCE_ID, and GITHUB_REPOSITORY are required.", file=sys.stderr)
        return 1

    remote_script = f"""#!/usr/bin/env bash
set -euo pipefail
export APP_DIR={shell_quote(app_dir)}
export APP_ENV_FILE_B64={shell_quote(app_env_b64)}
export GITHUB_REPO={shell_quote(github_repo)}
export GIT_DEPLOY_TOKEN={shell_quote(git_token)}
export DEPLOY_BRANCH={shell_quote(deploy_branch)}
DEPLOY_USER="${{SUDO_USER:-ubuntu}}"

# --- One-time host setup (no-ops once done) ---------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "Installing git..."
  apt-get update -y && apt-get install -y git
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true
# runuser below starts a fresh session, which picks this group up immediately.
usermod -aG docker "${{DEPLOY_USER}}" || true

mkdir -p "${{APP_DIR}}"
chown -R "${{DEPLOY_USER}}:${{DEPLOY_USER}}" "${{APP_DIR}}"

# --- Check out the branch and deploy it, as the deploy user ----------------------------
runuser -u "${{DEPLOY_USER}}" -- env \\
  APP_DIR="${{APP_DIR}}" \\
  APP_ENV_FILE_B64="${{APP_ENV_FILE_B64}}" \\
  GITHUB_REPO="${{GITHUB_REPO}}" \\
  GIT_DEPLOY_TOKEN="${{GIT_DEPLOY_TOKEN}}" \\
  DEPLOY_BRANCH="${{DEPLOY_BRANCH}}" \\
  bash -lc '
set -euo pipefail
APP_DIR="${{APP_DIR/#\\~/$HOME}}"
cd "${{APP_DIR}}"

if [ ! -d .git ]; then
  git init
  git remote add origin "https://github.com/${{GITHUB_REPO}}.git"
fi

if [ -n "${{GIT_DEPLOY_TOKEN}}" ]; then
  git remote set-url origin "https://x-access-token:${{GIT_DEPLOY_TOKEN}}@github.com/${{GITHUB_REPO}}.git"
else
  git remote set-url origin "https://github.com/${{GITHUB_REPO}}.git"
fi

git fetch --depth 1 origin "${{DEPLOY_BRANCH}}"
git checkout -B "${{DEPLOY_BRANCH}}" FETCH_HEAD
git reset --hard FETCH_HEAD
echo "Deploying $(git rev-parse --short HEAD) from ${{DEPLOY_BRANCH}}"

chmod +x ./scripts/deploy-ec2.sh ./scripts/configure-keycloak.sh
./scripts/deploy-ec2.sh
'
"""

    script_b64 = base64.b64encode(remote_script.encode("utf-8")).decode("ascii")
    params = {"commands": [f"echo {script_b64} | base64 -d | bash"]}

    if len(json.dumps(params)) > MAX_PARAMS_BYTES:
        print("Generated SSM payload is too large. Shorten APP_ENV_FILE_B64 or use an on-instance .env.",
              file=sys.stderr)
        return 1

    json.dump(params, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
