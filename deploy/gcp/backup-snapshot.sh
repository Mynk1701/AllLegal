#!/usr/bin/env bash
# backup-snapshot.sh — take an OpenSearch snapshot and sync it to GCS.
#
# MANDATORY, not optional. After the Oracle VM is decommissioned this cluster
# holds the ONLY live copy of the corpus, and the index no longer stores
# chunk_embedding in _source, so a lost index cannot be rebuilt from itself —
# only from legal-engine/output/{03_enriched,04_embedded} or a fresh (paid)
# Voyage embedding run.
#
# Uses the _snapshot API rather than tarring the data volume: tarring a LIVE
# volume can capture inconsistent Lucene state. This was listed as a known
# follow-up in deploy/oracle/README.md but was impossible there — that box had
# 3.8 GB of free disk. The 100 GB GCP disk makes a filesystem repo viable.
#
# Prerequisites (one-off):
#   sudo mkdir -p /mnt/snapshots && sudo chown 1000:1000 /mnt/snapshots
#   (path.repo=/mnt/snapshots is already set in docker-compose.yml, and the
#    directory is bind-mounted into the container at the same path)
#   gcloud storage buckets create gs://nirnay-opensearch-backups --location=us-west1
#
# Cron (nightly at 03:15):
#   15 3 * * * /home/$USER/law-opensearch/backup-snapshot.sh >> /var/log/os-backup.log 2>&1
#
# Usage: ./backup-snapshot.sh [host]
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

HOST="${1:-https://localhost:9200}"
REPO="${REPO:-local}"
BUCKET="${BUCKET:-gs://nirnay-opensearch-backups}"
SNAPSHOT="snap-$(date +%F-%H%M)"
PW="${OPENSEARCH_INITIAL_ADMIN_PASSWORD:?set OPENSEARCH_INITIAL_ADMIN_PASSWORD in deploy/gcp/.env}"
CURL=(curl -sk -u "admin:$PW")

# Register the repo if absent. Idempotent: a repeat PUT with identical settings
# is a no-op, so this is safe to leave in the nightly path.
if ! "${CURL[@]}" -f "$HOST/_snapshot/$REPO" >/dev/null 2>&1; then
  echo "[backup] registering filesystem repo '$REPO' at /mnt/snapshots ..."
  "${CURL[@]}" -f -XPUT "$HOST/_snapshot/$REPO" -H 'Content-Type: application/json' \
    -d '{"type":"fs","settings":{"location":"/mnt/snapshots","compress":true}}' >/dev/null
fi

echo "[backup] taking snapshot $SNAPSHOT (wait_for_completion) ..."
"${CURL[@]}" -f -XPUT "$HOST/_snapshot/$REPO/$SNAPSHOT?wait_for_completion=true" \
  -H 'Content-Type: application/json' \
  -d '{"indices":"case_chunks_v2","include_global_state":false}' >/dev/null

state=$("${CURL[@]}" -f "$HOST/_snapshot/$REPO/$SNAPSHOT" | grep -o '"state":"[A-Z_]*"' | head -1 | cut -d'"' -f4)
echo "[backup]   state=$state"
if [ "$state" != "SUCCESS" ]; then
  echo "[backup] FAIL: snapshot state is '$state', not SUCCESS"; exit 1
fi

echo "[backup] syncing /mnt/snapshots -> $BUCKET/snapshots ..."
gcloud storage rsync -r /mnt/snapshots "$BUCKET/snapshots"

echo "[backup] pruning local snapshots older than 7 days (GCS keeps the long tail) ..."
for old in $("${CURL[@]}" -f "$HOST/_snapshot/$REPO/_all" \
             | grep -o '"snapshot":"[^"]*"' | cut -d'"' -f4 \
             | sort | head -n -7); do
  echo "[backup]   deleting $old"
  "${CURL[@]}" -f -XDELETE "$HOST/_snapshot/$REPO/$old" >/dev/null
done

echo "[backup] OK: $SNAPSHOT in $BUCKET/snapshots"
echo "[backup] REMINDER: an unrestored backup is not a backup. Test-restore periodically:"
echo "[backup]   POST $HOST/_snapshot/$REPO/$SNAPSHOT/_restore"
echo "[backup]        {\"indices\":\"case_chunks_v2\",\"rename_pattern\":\"(.+)\",\"rename_replacement\":\"restore_test_\$1\"}"
