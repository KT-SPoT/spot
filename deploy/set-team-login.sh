#!/usr/bin/env bash
# Run interactively on the VM. Password never goes into arguments, history or stdout.
set -euo pipefail
test "$(id -u)" = 0 || { echo 'Run with sudo'; exit 1; }
cd /opt/spot
if test -f deploy/secrets/team-login-ready; then
  echo 'Login is already configured; review before changing it.'; exit 1
fi
. deploy/hosting.env
compose_args=(--env-file deploy/hosting.env -f deploy/compose.yaml)
if test -n "${SPOT_N8N_DOMAIN:-}"; then
  compose_args+=(-f deploy/compose.n8n.yaml)
fi
compose_args+=(-f deploy/compose.server.yaml)
read -r -s -p 'New SPoT team password (at least 12 characters): ' team_password </dev/tty
printf '\n' >/dev/tty
read -r -s -p 'Repeat password: ' team_confirmation </dev/tty
printf '\n' >/dev/tty
test "${#team_password}" -ge 12 && test "$team_password" = "$team_confirmation" || {
  unset team_password team_confirmation
  echo 'Passwords did not match or were too short. Run again.'; exit 1
}
# Caddy's non-interactive reader requires a newline-terminated password.
team_hash=$(printf '%s\n' "$team_password" | docker run --rm -i --network none "$SPOT_PROXY_IMAGE" caddy hash-password --bcrypt-cost 12)
unset team_password team_confirmation
test -n "$team_hash"
umask 077
printf 'basic_auth {\n    team %s\n}\n' "$team_hash" > deploy/secrets/web-login.caddy
unset team_hash
chmod 600 deploy/secrets/web-login.caddy
# Keep the staged bind mount's inode while changing its contents.
if test -n "${SPOT_N8N_DOMAIN:-}"; then
  cp deploy/Caddyfile.n8n deploy/Caddyfile.stage
else
  cp deploy/Caddyfile deploy/Caddyfile.stage
fi
docker compose "${compose_args[@]}" exec -T proxy caddy validate --config /etc/caddy/Caddyfile
docker compose "${compose_args[@]}" exec -T proxy caddy reload --config /etc/caddy/Caddyfile
touch deploy/secrets/team-login-ready
echo 'Team login is ready. Username: team'
