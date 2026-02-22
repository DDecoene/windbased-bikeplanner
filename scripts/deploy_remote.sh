#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/deploy_remote.sh <commit> [host] [remote_dir] [ssh_key] [--yes]
# Example:
#   ./scripts/deploy_remote.sh d1608a44097392f896eeb9df3d70ddb30ea28b5e root@46.225.178.121 /opt/rgwnd ~/.ssh/gitlab_dennisdecoene

COMMIT=${1:-}
HOST=${2:-root@46.225.178.121}
REMOTE_DIR=${3:-/opt/rgwnd}
SSH_KEY=${4:-$HOME/.ssh/gitlab_dennisdecoene}
CONFIRM_FLAG=${5:-}

if [ -z "$COMMIT" ]; then
  echo "Error: commit hash required."
  echo "Usage: $0 <commit> [host] [remote_dir] [ssh_key] [--yes]"
  exit 2
fi

if [ "$CONFIRM_FLAG" != "--yes" ]; then
  echo "About to deploy commit $COMMIT to $HOST:$REMOTE_DIR"
  read -p "Continue? (type 'yes' to proceed) " ans
  if [ "$ans" != "yes" ]; then
    echo "Aborted."
    exit 1
  fi
fi

echo "Deploying $COMMIT to $HOST:$REMOTE_DIR using key $SSH_KEY"

SSH_CMD="cd $REMOTE_DIR && git fetch --all --tags && git checkout --force $COMMIT && git reset --hard $COMMIT && docker compose up --build -d --remove-orphans"

ssh -i "$SSH_KEY" "$HOST" "$SSH_CMD"

echo "Verifying deployment..."
ssh -i "$SSH_KEY" "$HOST" "cd $REMOTE_DIR && git rev-parse HEAD && docker compose ps --quiet || true"

echo "Done. If you want logs, run:" 
echo "  ssh -i $SSH_KEY $HOST 'cd $REMOTE_DIR && docker compose logs --tail 200 backend'"
