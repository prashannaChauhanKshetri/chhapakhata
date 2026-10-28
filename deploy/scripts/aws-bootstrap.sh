#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu 24.04 server (e.g. AWS EC2 t3.small):
# 2 GB swap (building the app needs more than 2 GB of memory at peak), Docker
# with the compose plugin, and git. Run with sudo:  sudo ./aws-bootstrap.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo." >&2
  exit 1
fi

if ! swapon --show | grep -q '^/swapfile'; then
  echo "Adding 2 GB of swap..."
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "Installing Docker and git..."
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io docker-compose-v2 git
systemctl enable --now docker

# Let the login user run docker without sudo (takes effect at the next login).
login_user="${SUDO_USER:-ubuntu}"
usermod -aG docker "$login_user"

echo
echo "Done. Log out and back in, then follow docs/deploy-aws.md from 'Clone the code'."
