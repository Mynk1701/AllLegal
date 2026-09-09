#!/usr/bin/env bash
# restore.sh — atomically load a data tarball into the EXISTING external volume,
# bring the stack up, and verify it actually holds data.
#
# Use this for ANY data (re)load instead of doing the steps by hand. It bundles
# the step that got skipped on 2026-06-24 (extract data into the volume) with the
# verification, so the cluster can never come up silently empty again.
#
# The tarball must be a gzip of the OpenSearch data dir contents
# (./nodes/, ./*.conf, ...) — i.e. created with:
#     tar -czf opensearch-data.tar.gz -C /var/lib/docker/volumes/opensearch-data/_data .
#
# Usage:  sudo ./restore.sh /home/opc/opensearch-data.tar.gz
set -euo pipefail

TARBALL="${1:?usage: restore.sh <path-to-opensearch-data.tar.gz>}"
VOL=/var/lib/docker/volumes/opensearch-data/_data
HERE="$(cd "$(dirname "$0")" && pwd)"

# Security plugin is on (auth + self-signed TLS); read admin creds for the wait loop.
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a
PW="${OPENSEARCH_INITIAL_ADMIN_PASSWORD:?set OPENSEARCH_INITIAL_ADMIN_PASSWORD in deploy/oracle/.env}"

if [ ! -f "$TARBALL" ]; then echo "[restore] FAIL: no such file: $TARBALL"; exit 1; fi

echo "[restore] verifying tarball integrity ..."
gzip -t "$TARBALL"

echo "[restore] stopping stack (external volume is preserved) ..."
docker compose -f "$HERE/docker-compose.yml" down

echo "[restore] wiping volume contents and extracting ..."
find "$VOL" -mindepth 1 -delete
tar -xzf "$TARBALL" -C "$VOL"
chown -R 1000:1000 "$VOL"                       # 1000 = opensearch user inside the container
echo "[restore]   volume size now: $(du -sh "$VOL" | cut -f1)"

echo "[restore] starting stack ..."
docker compose -f "$HERE/docker-compose.yml" up -d

echo "[restore] waiting for shards to recover (green/yellow, not just reachable) ..."
# A freshly-started node returns 200 with status=red while it replays the
# translog — so wait for green/yellow, not merely for the endpoint to respond,
# or the smoke check below fires too early and false-fails on a transient red.
# Security plugin init (securityadmin) adds a few seconds before the API accepts
# authed requests, so allow generous retries on connection refusal too.
for i in $(seq 1 60); do
  s=$(curl -sk -u "admin:$PW" https://localhost:9200/_cluster/health | grep -o '"status":"[a-z]*"' | cut -d'"' -f4 || true)
  case "$s" in green|yellow) break;; esac
  sleep 3
done

echo "[restore] verifying data is present ..."
"$HERE/smoke-check.sh"
echo "[restore] DONE — cluster is up and holds data."
