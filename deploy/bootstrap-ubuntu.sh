#!/usr/bin/env bash
# Ubuntu 24.04 host preparation. Contains no application credentials.
set -euo pipefail
test "$(id -u)" = 0 || { echo 'Run with sudo'; exit 1; }
. /etc/os-release
test "$ID" = ubuntu && test "$VERSION_ID" = 24.04 || {
  echo 'This bootstrap requires Ubuntu 24.04'; exit 1;
}
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update -qq
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
# A small VM needs reserve memory during builds; swap is not a RAM upgrade.
if ! swapon --show=NAME --noheadings | grep -q .; then
  if test -e /spot-swapfile; then
    echo 'Existing /spot-swapfile requires manual review'; exit 1;
  fi
  fallocate -l 2G /spot-swapfile
  chmod 600 /spot-swapfile
  mkswap /spot-swapfile
  swapon /spot-swapfile
  echo '/spot-swapfile none swap sw 0 0' >> /etc/fstab
fi
install -m 0755 -d /opt/spot
install -m 0700 -d /opt/spot/deploy/secrets
docker --version
docker compose version
systemctl is-active docker
free -m
