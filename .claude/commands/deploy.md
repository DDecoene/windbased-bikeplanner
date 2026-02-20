---
name: deploy
description: Deploy to production Hetzner VPS via SSH
allowed-tools:
  - Bash
---

Deploy the current `main` branch to the production Hetzner VPS (rgwnd.app).

## Steps

### 1. Pre-flight check

Verify the local branch is `main` and there are no uncommitted changes:

```bash
git status
git log --oneline -3
```

If there are uncommitted changes, stop and tell the user to commit or stash first.

### 2. SSH into the VPS and deploy

Run all deployment steps in a single SSH command:

```bash
ssh rgwnd 'cd /root/windbased-bikeplanner && git pull && docker compose up --build -d --remove-orphans 2>&1'
```

The SSH host alias `rgwnd` must be configured in `~/.ssh/config`. If the connection fails, inform the user and suggest they check their SSH config or VPN.

### 3. Verify services are up

After the build, check that all services are healthy:

```bash
ssh rgwnd 'docker compose ps'
```

Report which services are running and flag any that are not in a healthy/running state.

### 4. Smoke test

Do a quick HTTP check to verify the live site responds:

```bash
curl -s -o /dev/null -w "%{http_code}" https://rgwnd.app
```

A `200` or `301` is success. Report the result to the user.

## Notes

- The VPS is a Hetzner CX23 at IP `46.225.178.121`, Nuremberg. SSH alias: `rgwnd`.
- Services: `caddy`, `backend`, `frontend`, `watchdog`.
- Only changed services are rebuilt by Docker Compose — unchanged ones restart quickly.
- If the build fails due to missing `.env`, tell the user the `.env` file may be missing on the server.
- Do NOT run `git push` — assume the user has already pushed before deploying.
