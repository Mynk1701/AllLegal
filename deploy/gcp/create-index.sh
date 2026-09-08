#!/usr/bin/env bash
# create-index.sh — create case_chunks_v2 from the versioned mapping.
#
# Adapted from legal-engine/docker/opensearch/init/create_index.sh. Two
# deliberate differences:
#
#   1. Speaks HTTPS + basic auth (the security plugin is on — see
#      docker-compose.yml), where the pipeline's version assumed a plain,
#      no-auth dev cluster.
#   2. Does NOT add the `case_chunks` alias. On the pipeline's version, create
#      and alias were one step. Here the alias flip is the cutover itself: the
#      app queries the alias (settings.OPENSEARCH_INDEX = "case_chunks"), so
#      attaching it before the data is copied and verified would point live
#      traffic at an empty index. Flip it by hand after §6.1/§6.2 verification:
#
#        curl -sk -u admin:"$PW" -XPOST https://localhost:9200/_aliases \
#          -H 'Content-Type: application/json' \
#          -d '{"actions":[{"add":{"index":"case_chunks_v2","alias":"case_chunks"}}]}'
#
# v2 (not v1) because the mapping changed: `_source.excludes: [chunk_embedding]`.
# The vector is still indexed into the HNSW graph exactly as before — only the
# redundant JSON copy in _source is dropped. Measured on the v1 index: 24,890
# bytes/doc with the stored copy vs 3,202 without, i.e. ~21.7 KB/doc of pure
# duplication that the app never reads (SOURCE_FIELDS in
# app/services/opensearch_service.py omits chunk_embedding).
#
# Idempotent: skips creation if the index already exists.
#
# Usage: ./create-index.sh [host]     (default host: https://localhost:9200)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

HOST="${1:-https://localhost:9200}"
INDEX="${INDEX:-case_chunks_v2}"
MAPPING="$HERE/case_chunks_v2.json"
PW="${OPENSEARCH_INITIAL_ADMIN_PASSWORD:?set OPENSEARCH_INITIAL_ADMIN_PASSWORD in deploy/gcp/.env}"
CURL=(curl -sk -u "admin:$PW")   # -k: demo certs are self-signed

[ -f "$MAPPING" ] || { echo "[create-index] FAIL: mapping not found: $MAPPING"; exit 1; }

echo "[create-index] waiting for OpenSearch at ${HOST} ..."
for i in $(seq 1 60); do
  if "${CURL[@]}" -f "${HOST}/_cluster/health" >/dev/null 2>&1; then break; fi
  if [ "$i" -eq 60 ]; then
    echo "[create-index] FAIL: not reachable after 60 attempts (security plugin init takes ~60-90s on a cold start)" >&2
    exit 1
  fi
  sleep 2
done
echo "[create-index] OpenSearch is up."

code=$("${CURL[@]}" -o /dev/null -w '%{http_code}' "${HOST}/${INDEX}")
if [ "$code" = "200" ]; then
  echo "[create-index] index ${INDEX} already exists — skipping create"
else
  echo "[create-index] creating index ${INDEX} ..."
  "${CURL[@]}" -f -X PUT "${HOST}/${INDEX}" \
    -H 'Content-Type: application/json' \
    --data-binary "@${MAPPING}"
  echo
fi

echo "[create-index] verifying _source exclusion is in place ..."
if ! "${CURL[@]}" -f "${HOST}/${INDEX}/_mapping" | grep -q '"excludes"'; then
  echo "[create-index] FAIL: ${INDEX} has no _source.excludes — it would store embeddings twice." >&2
  echo "[create-index]       Delete the index and re-run, or the copy will land at ~11.6 GB." >&2
  exit 1
fi

echo "[create-index] OK: ${INDEX} exists with chunk_embedding excluded from _source."
echo "[create-index] NOTE: alias 'case_chunks' is NOT attached yet — that is the cutover step."
