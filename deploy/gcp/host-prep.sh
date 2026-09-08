#!/usr/bin/env bash
# host-prep.sh — one-shot host preparation for a fresh Ubuntu 24.04 GCE VM.
#
# Installs Docker, sets the kernel limit OpenSearch requires, and creates the
# data volume + snapshot dir. Idempotent: safe to re-run.
#
# Run once on the VM, then LOG OUT AND BACK IN (docker group membership only
# applies to a new login session).
set -euo pipefail

echo "[prep] disk:"; df -h / | tail -1

echo "[prep] vm.max_map_count (required by OpenSearch, persisted across reboots) ..."
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opensearch.conf >/dev/null
sudo sysctl --system >/dev/null
echo "[prep]   $(sysctl -n vm.max_map_count)"

if ! command -v docker >/dev/null 2>&1; then
  echo "[prep] installing Docker from the official apt repo ..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin python3-pip
else
  echo "[prep] Docker already installed — skipping"
fi

echo "[prep] data volume + snapshot dir ..."
# 1000 = the opensearch user inside the container
sudo docker volume create opensearch-data >/dev/null
sudo mkdir -p /mnt/snapshots && sudo chown 1000:1000 /mnt/snapshots

sudo usermod -aG docker "$USER"

echo
echo "[prep] DONE. Now LOG OUT and back in, then verify with:"
echo "         docker ps && sysctl vm.max_map_count"
