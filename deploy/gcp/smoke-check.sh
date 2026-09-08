#!/usr/bin/env bash
# smoke-check.sh — assert OpenSearch is not just UP, but actually HOLDS DATA.
#
# Carried over unchanged in spirit from deploy/oracle/smoke-check.sh. It exists
# because on 2026-06-24 the Oracle cluster was verified as "container up" but
# never as "data present", so an EMPTY cluster served traffic for ~20h before
# /api/facets started 500ing. Run this after every (re)start. Exits non-zero
# (loudly) on an empty/broken cluster so a wrapping script or human notices.
#
# Auth/TLS: the security plugin is on (auth + self-signed TLS), so we talk https
# with admin creds. The password is read from deploy/gcp/.env
# (OPENSEARCH_INITIAL_ADMIN_PASSWORD), or pass it via that env var.
#
# Checks the ALIAS, not the index, because the alias is what the app queries
# (settings.OPENSEARCH_INDEX = "case_chunks"). Before the cutover alias flip
# this will correctly FAIL — that is not a bug, it means you have not cut over
# yet. To smoke the new index ahead of the flip: ALIAS=case_chunks_v2 ./smoke-check.sh
#
# Usage: ./smoke-check.sh [host]     (default host: https://localhost:9200)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

HOST="${1:-https://localhost:9200}"
ALIAS="${ALIAS:-case_chunks}"
# Guards against a half-finished migration being declared good. The v1 corpus
# was 465,398 docs; anything far below that means the copy did not complete.
MIN_DOCS="${MIN_DOCS:-465398}"
PW="${OPENSEARCH_INITIAL_ADMIN_PASSWORD:?set OPENSEARCH_INITIAL_ADMIN_PASSWORD in deploy/gcp/.env}"
CURL=(curl -sk -u "admin:$PW")   # -k: demo certs are self-signed

echo "[smoke] cluster health @ $HOST ..."
status=$("${CURL[@]}" -f "$HOST/_cluster/health" | grep -o '"status":"[a-z]*"' | cut -d'"' -f4)
echo "[smoke]   status=$status"
if [ "$status" != "green" ] && [ "$status" != "yellow" ]; then
  echo "[smoke] FAIL: cluster status is '$status' (not green/yellow)"; exit 1
fi

echo "[smoke] '$ALIAS' resolves ..."
if ! "${CURL[@]}" -f "$HOST/$ALIAS" >/dev/null; then
  echo "[smoke] FAIL: '$ALIAS' is missing (not yet cut over? see create-index.sh)"; exit 1
fi

echo "[smoke] document count via '$ALIAS' ..."
count=$("${CURL[@]}" -f "$HOST/$ALIAS/_count" | grep -o '"count":[0-9]*' | cut -d: -f2)
echo "[smoke]   count=${count:-0} (expected >= $MIN_DOCS)"
if [ "${count:-0}" -le 0 ]; then
  echo "[smoke] FAIL: '$ALIAS' has 0 docs — data not loaded (run migrate_index.py)"; exit 1
fi
if [ "${count:-0}" -lt "$MIN_DOCS" ]; then
  echo "[smoke] FAIL: '$ALIAS' has $count docs, fewer than the expected $MIN_DOCS — migration incomplete"; exit 1
fi

echo "[smoke] kNN is queryable (dimension + graph loaded) ..."
# Exercises the HNSW path and the 1024-dim check without needing a Voyage call.
# We assert the request succeeds, not what it ranks.
# MUST be non-zero: the index uses space_type cosinesimil, and cosine similarity
# is undefined for a zero-magnitude vector — OpenSearch rejects it outright with
# "zero vector is not supported when space type is [cosinesimil]".
vec=$(python3 -c 'print("[" + ",".join(["0.1"]*1024) + "]")')
if ! "${CURL[@]}" -f -XPOST "$HOST/$ALIAS/_search" -H 'Content-Type: application/json' \
     -d "{\"size\":1,\"_source\":[\"case_id\"],\"query\":{\"knn\":{\"chunk_embedding\":{\"vector\":$vec,\"k\":10}}}}" >/dev/null; then
  echo "[smoke] FAIL: kNN query rejected — check the chunk_embedding mapping"; exit 1
fi

echo "[smoke] OK: '$ALIAS' resolves, holds ${count} docs, and serves kNN queries."
