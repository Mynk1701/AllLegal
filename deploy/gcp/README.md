# Google Cloud — self-hosted OpenSearch

Single-node OpenSearch backing AllLegal search, on a GCE VM in `us-west1`
(Oregon, co-located with the Render backend). The Render backend connects over
the static external IP (`OPENSEARCH_HOST`).

| | |
|---|---|
| VM public IP | `34.187.155.254` — the reserved static address `opensearch-ip` |
| Region / zone | `us-west1` / `us-west1-b` (Render runs in Oregon; each `/api/search` makes 2–4 round trips here) |
| Machine | `e2-highmem-2` — 2 vCPU, 16 GB RAM, 100 GB `pd-balanced` |
| SSH | `gcloud compute ssh law-opensearch --zone=us-west1-b` |
| OpenSearch | `https://34.187.155.254:9200` — **auth required** (security plugin on, self-signed TLS) |
| Admin creds | user `admin`, password in VM-local `.env` (NOT in git) |
| Container | `law-opensearch` (image `opensearchproject/opensearch:2.19.5`) |
| Data volume | `opensearch-data` (host: `/var/lib/docker/volumes/opensearch-data/_data`) |
| Snapshot repo | `local` → `/mnt/snapshots` → `gs://nirnay-opensearch-backups` |
| Index / alias | `case_chunks_v2`, alias `case_chunks` (the app queries the alias) |
| Files on VM | `/home/<user>/law-opensearch/` |

## ⚠️ Only ever write FULL documents to `case_chunks_v2`

`case_chunks_v2` sets `_source: { excludes: ["chunk_embedding"] }`. The vector is
still indexed into the HNSW graph and search is unchanged — but the vector is no
longer *stored*, and that makes two normally-safe operations destructive:

- **`update_by_query` / partial `_update` will silently wipe vectors.** Both read
  `_source`, apply the patch, and re-index the result. With the embedding absent
  from `_source`, every document they touch comes back vectorless — no error, no
  warning, and semantic search quietly degrades. A one-liner like "backfill
  `case_type` across the corpus" would do real damage.
- **`_reindex` out of this index produces vectorless documents.** To change the
  mapping (different `m` / `ef_construction`, a new dimension, a re-analyzed
  field), rebuild from the pipeline instead — see "Rebuilding from scratch".

The pipeline is already safe: `stage_05_index.py` bulk-writes with
`_op_type: "index"`, a full replacement carrying `chunk_embedding` in the body.
**Onboarding new chunks needs no change at all.** Keep it that way.

Why the exclusion exists: measured on the v1 index, a document was 24,890 bytes
with the stored copy and 3,202 bytes without — ~21.7 KB/doc the app has never
read (`SOURCE_FIELDS` in `app/services/opensearch_service.py` omits
`chunk_embedding`).

**On-disk saving is smaller than that response-size gap suggests.** Lucene
compresses stored fields, so a 1024-float JSON array costs far less on disk than
in an API response. Measured during the migration: **18.2 KB/doc in v2 vs
25.5 KB/doc in v1 — a 29% reduction, giving ~8 GB rather than the ~5 GB an
uncompressed extrapolation predicts.** Still the right call (8 GB is fully
cacheable where 11.6 GB was not), but size the box against 8 GB, not 5 GB.

## Everyday ops (on the VM, in `~/law-opensearch/`)

```bash
docker compose up -d         # start / recreate (reuses the existing data volume)
docker compose ps            # status + health
docker compose logs -f       # logs
docker compose down          # stop + remove container — does NOT delete data
./smoke-check.sh             # assert the cluster actually HOLDS data + serves kNN
./backup-snapshot.sh         # snapshot -> /mnt/snapshots -> GCS
```

## Sizing rationale

RAM, not CPU, is the constraint at this scale. The Lucene k-NN engine keeps
vectors **off-heap in mmap'd Lucene segments** — `_plugins/_knn/stats` reports
`graph_memory_usage: 0`, i.e. the native KNN cache is unused — so query latency
is governed by whether the OS page cache holds the index.

16 GB with a 4 GB heap leaves ~11-12 GB of page cache for a 4.4 GB index: fully
resident with ~2.5x growth headroom (roughly 1.2M chunks) before pressure returns.
The previous Oracle host had ~3 GB of cache for an 11.6 GB index, which is what
produced the cold-cache `ReadTimeout` → 502s fixed in commit `5a5cce1`.

Revisit the machine size when the corpus approaches ~1M chunks; `e2-highmem-4`
(4 vCPU / 32 GB) is the next step up. Re-run the force-merge after any large
ingest — segment count, not corpus size, is what degrades kNN latency first.

Do not raise `OPENSEARCH_JAVA_OPTS` past `-Xmx8g`: heap is taken *from* the page
cache that actually matters here.

## Security posture

- **Security plugin on.** Every request needs HTTP basic auth; the HTTP layer is
  TLS (demo self-signed certs, hence `-k` / `OPENSEARCH_VERIFY_CERTS=false`).
- **VPC firewall default-denies ingress.** `tcp:9200` is open only to Render's
  outbound CIDRs and the admin IP (`opensearch-from-render`,
  `opensearch-from-admin`). Render's egress IPs are **shared** across tenants, so
  auth — not the allowlist — remains the real boundary.
- The admin password lives in exactly two places: the VM-local `.env` (chmod
  600, gitignored) and Render's environment variables. Never commit it.

This exists because the predecessor cluster on Oracle was wiped **twice** by
automated ransomware bots while running open with no auth (2026-06-26; a
`read_me` index demanding 0.0041 BTC). No ransom was paid. Do not disable the
security plugin, and do not widen the firewall to `0.0.0.0/0`.

## App configuration (Render)

| Var | Value |
|---|---|
| `OPENSEARCH_HOST` | `34.187.155.254` |
| `OPENSEARCH_PORT` | `9200` |
| `OPENSEARCH_USE_SSL` | `true` |
| `OPENSEARCH_VERIFY_CERTS` | `false` |
| `OPENSEARCH_USER` | `admin` |
| `OPENSEARCH_PASSWORD` | the VM `.env` value |
| `OPENSEARCH_INDEX` | `case_chunks` (the alias — leave as is) |

Failure modes are cleanly distinguishable: `ConnectTimeoutError` means the
firewall/CIDR is wrong, `401` means the password is wrong.

## Restoring

```bash
# list what's available
curl -sk -u admin:"$PW" https://localhost:9200/_snapshot/local/_all

# restore into a throwaway name first — never straight over the live index
curl -sk -u admin:"$PW" -XPOST https://localhost:9200/_snapshot/local/<snap>/_restore \
  -H 'Content-Type: application/json' \
  -d '{"indices":"case_chunks_v2","rename_pattern":"(.+)","rename_replacement":"restore_test_$1"}'
```

If GCS holds the snapshot but the VM does not, `gcloud storage rsync -r
gs://nirnay-opensearch-backups/snapshots /mnt/snapshots` first, then restore.

## Rebuilding from scratch

The index cannot regenerate its own vectors (see the warning above). The rebuild
path is the pipeline:

1. `gcloud storage rsync -r gs://nirnay-opensearch-backups/embeddings/03_enriched legal-engine/output/03_enriched`
2. same for `04_embedded`
3. `./create-index.sh` to make an empty `case_chunks_v2`
4. run `legal-engine` `stage_05_index.py` against it (needs `http_auth` +
   `verify_certs=False` added — it currently constructs a plain no-auth client at
   `stage_05_index.py:293`)

`stage_05_index.py` needs **both** directories: `build_actions()` joins enriched
chunks with the `.npz` vectors.

## History

- **`deploy/oracle/`** is kept in the repo as the predecessor's documentation. It
  carries two incident write-ups worth reading before touching this stack: the
  2026-06-24 empty-volume incident (why the data volume is `external: true` and
  why `smoke-check.sh` asserts data, not liveness) and the 2026-06-26 ransomware
  wipe (why the security plugin is on).
- **Why we left Oracle:** the Always Free Ampere A1 allowance was cut from
  4 OCPU/24 GB to 2 OCPU/12 GB on 2026-06-15, with over-limit instances
  terminated from 2026-08-18. That capped the host at 12 GB for an 11.6 GB index
  with no free-tier path to more RAM.

## Known follow-ups

- **`k` is not scale-invariant.** `total_cases` is computed by a
  `cardinality(case_id)` agg that runs over only the `k` retrieved chunks, so the
  count shown to users is a function of `KNN_K_CEILING` rather than of the
  corpus — measured: k=500/1500/5000 → 388/1058/3066 distinct cases. Fix is to
  take the total from a filter-only aggregation (measured at 167 ms over the full
  corpus) and derive `k` from page depth × mean fanout. See §10 of the migration
  plan.
- **A real TLS certificate.** A domain plus Caddy in front of OpenSearch would
  allow `OPENSEARCH_VERIFY_CERTS=true` and remove the last `-k` in the stack.
- **Re-measure the k-vs-latency curve** on this host (1 segment, index fully
  cached) and update the comment block in `app/core/config.py:58-64`, which
  records Oracle numbers (k=1500 → 1.27 s, k=5000 → 2.61 s warm, 2026-09-06).
