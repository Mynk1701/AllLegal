#!/usr/bin/env bash
# smoke-check.sh — assert OpenSearch is not just UP, but actually HOLDS DATA.
#
# This is the check that was missing on 2026-06-24: we verified "container up"
# but never "data present", so an empty cluster ran unnoticed for ~20h. Run this
# after every (re)start. Exits non-zero (loudly) on an empty/broken cluster so a
# wrapping script or human notices immediately.
#
# Auth/TLS: the cluster now runs the security plugin (auth + self-signed TLS), so
# we talk https with admin creds. The password is read from deploy/oracle/.env
# (OPENSEARCH_INITIAL_ADMIN_PASSWORD), or pass it via that env var.
#
# Usage: ./smoke-check.sh [host]     (default host: https://localhost:9200)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

HOST="${1:-https://localhost:9200}"
ALIAS="case_chunks"
PW="${OPENSEARCH_INITIAL_ADMIN_PASSWORD:?set OPENSEARCH_INITIAL_ADMIN_PASSWORD in deploy/oracle/.env}"
CURL=(curl -sk -u "admin:$PW")   # -k: demo certs are self-signed

echo "[smoke] cluster health @ $HOST ..."
status=$("${CURL[@]}" -f "$HOST/_cluster/health" | grep -o '"status":"[a-z]*"' | cut -d'"' -f4)
echo "[smoke]   status=$status"
if [ "$status" != "green" ] && [ "$status" != "yellow" ]; then
  echo "[smoke] FAIL: cluster status is '$status' (not green/yellow)"; exit 1
fi

echo "[smoke] alias '$ALIAS' resolves ..."
if ! "${CURL[@]}" -f "$HOST/_alias/$ALIAS" >/dev/null; then
  echo "[smoke] FAIL: alias '$ALIAS' is missing"; exit 1
fi

echo "[smoke] document count via alias ..."
count=$("${CURL[@]}" -f "$HOST/$ALIAS/_count" | grep -o '"count":[0-9]*' | cut -d: -f2)
echo "[smoke]   count=${count:-0}"
if [ "${count:-0}" -le 0 ]; then
  echo "[smoke] FAIL: alias '$ALIAS' has 0 docs — data not loaded (run restore.sh)"; exit 1
fi

echo "[smoke] OK: '$ALIAS' resolves and holds ${count} docs."
