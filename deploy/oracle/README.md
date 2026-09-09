# Oracle Cloud — self-hosted OpenSearch

Single-node OpenSearch backing AllLegal search, on the Oracle Cloud "Always Free"
Ampere VM. The Render backend connects to it over the public IP (`OPENSEARCH_HOST`).

| | |
|---|---|
| VM public IP | `80.225.202.124` |
| SSH | `ssh -i <ssh-key>.key opc@80.225.202.124` |
| OpenSearch | `https://80.225.202.124:9200` — **auth required** (security plugin on, self-signed TLS) |
| Admin creds | user `admin`, password in VM-local `deploy/oracle/.env` (NOT in git) |
| Container | `law-opensearch` (image `opensearchproject/opensearch:2.19.5`) |
| Data volume | `opensearch-data` (host: `/var/lib/docker/volumes/opensearch-data/_data`) |
| Index / alias | `case_chunks_v1`, alias `case_chunks` (the app queries the alias) |
| Files on VM | `/home/opc/law-opensearch/` |

## Everyday ops (on the VM, in `/home/opc/law-opensearch/`)

```bash
docker compose up -d         # start / recreate (reuses the existing data volume)
docker compose ps            # status + health
docker compose logs -f       # logs
docker compose down          # stop + remove container — does NOT delete data
./smoke-check.sh             # assert the cluster actually HOLDS data
```

## Restoring / loading data

```bash
sudo ./restore.sh /home/opc/opensearch-data.tar.gz
```

This wipes the volume, extracts the tarball, fixes ownership, starts the stack,
and runs the smoke check. Use it for any data (re)load — never extract by hand.

To make a fresh backup tarball from the live volume, snapshot is preferred (see
below), but a quick consistent-enough copy is:

```bash
docker compose down
sudo tar -czf ~/opensearch-data.tar.gz -C /var/lib/docker/volumes/opensearch-data/_data .
docker compose up -d
```

## Why this setup (incident note, 2026-06-24)

A manual `docker run` rebuild created a fresh empty volume and started the
container without re-loading data. Liveness looked fine ("container up"), so an
**empty cluster ran for ~20h** until `/api/facets` returned 500
(`index_not_found_exception: case_chunks`). Fixes baked in here:

1. **Compose with an `external` volume** — rebuilds always reattach the populated
   volume; Compose can't silently create an empty one.
2. **`smoke-check.sh`** — asserts data is present, not just that the cluster is up.
3. **`restore.sh`** — bundles extract + start + verify so the load step can't be skipped.

## Security incident #2 — ransomware wipe (2026-06-26)

The open, no-auth cluster was wiped a **second** time by an automated ransomware
bot (left a `read_me` index demanding 0.0041 BTC). We did NOT pay — the data is
in the tarball. Root cause: port 9200 was reachable by anyone with no auth.

**Fixed by enabling the security plugin** (removed `DISABLE_SECURITY_PLUGIN`):
- Every request now requires HTTP basic auth; the HTTP layer is TLS (demo
  self-signed certs). Mass-scan bots target *open* clusters and skip 401s.
- Admin password lives in VM-local `deploy/oracle/.env` (gitignored), consumed
  by Compose interpolation + the smoke/restore scripts.
- Verified externally: anonymous `GET`/`DELETE` → 401, plain http → refused.

App side: Render must set `OPENSEARCH_USE_SSL=true`, `OPENSEARCH_VERIFY_CERTS=false`,
`OPENSEARCH_USER=admin`, `OPENSEARCH_PASSWORD=<.env password>`.

## Known follow-ups (not yet done)

- **NSG allowlist (defense in depth):** auth now protects the cluster, but port
  9200 is still open to `0.0.0.0/0`. Optionally restrict the OCI NSG ingress to
  Render's egress IPs (+ admin IP). Note Render free-tier egress IPs are *shared*,
  so auth — not the IP allowlist — is the real boundary.
- **Backups:** currently a manual tarball. Move to the OpenSearch `_snapshot` API
  (a registered repo) — tarring a *live* volume can capture inconsistent Lucene
  state; snapshots are the correct, restore-tested mechanism.
- **`vm.max_map_count=262144`** is persisted in `/etc/sysctl.conf` (survives reboot).
