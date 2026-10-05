#!/usr/bin/env python3
"""Build the base64-encoded SSM bootstrap script for EC2 deployment."""

from __future__ import annotations

import base64
import json
import os
import sys


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def main() -> int:
    app_dir = os.environ.get("EC2_APP_DIR", "").strip()
    instance_id = os.environ.get("EC2_INSTANCE_ID", "").strip()
    github_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
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
export DEPLOY_BRANCH='deployment'
DEPLOY_USER="${{SUDO_USER:-ubuntu}}"
mkdir -p "${{APP_DIR}}"
chown -R "${{DEPLOY_USER}}:${{DEPLOY_USER}}" "${{APP_DIR}}"
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
fi

git fetch origin "${{DEPLOY_BRANCH}}"
git checkout "${{DEPLOY_BRANCH}}" || git checkout -b "${{DEPLOY_BRANCH}}" "origin/${{DEPLOY_BRANCH}}"
git reset --hard "origin/${{DEPLOY_BRANCH}}"

chmod +x ./scripts/deploy-ec2.sh ./scripts/configure-keycloak.sh
./scripts/deploy-ec2.sh
'
"""

    script_b64 = base64.b64encode(remote_script.encode("utf-8")).decode("ascii")
    params = {"commands": [f"echo {script_b64} | base64 -d | bash"]}

    if len(json.dumps(params)) > 97000:
        print("Generated SSM payload is too large. Shorten APP_ENV_FILE_B64 or use an on-instance .env.", file=sys.stderr)
        return 1

    json.dump(params, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
