#!/usr/bin/env python3
"""
migrate_index.py — copy case_chunks_v1 (Oracle) -> case_chunks_v2 (GCP).

Run this ON THE GCP VM: it sits on the receiving end of the HNSW build, which
is the actual bottleneck, and it keeps the ~11.6 GB transfer inside one hop.

WHY A SCRIPT AND NOT A NATIVE OPENSEARCH MECHANISM
--------------------------------------------------
Both native options were checked against the live 2.19.5 cluster and ruled out:

  * `_snapshot` restore — the source has NO repository-gcs / repository-s3
    plugin (its modules dir carries only repository-url, and GET /_snapshot
    returns {}), and a filesystem repo needs scratch space the source does not
    have (30 GB disk, 3.8 GB free).
  * `_reindex` from remote — the destination would have to accept the source's
    self-signed certificate, and OpenSearch 2.19.5 registers no `reindex.ssl.*`
    settings at all (confirmed via _cluster/settings?include_defaults=true).

A script sets verify_certs=False on both ends trivially, and it is what lets us
drop `_source.chunk_embedding` in the same pass: the vector is read from the
source, sent to the destination, indexed into the HNSW graph, and simply not
stored — the exclusion lives in the DESTINATION MAPPING (case_chunks_v2.json),
not here. Nothing in this file filters fields.

RESUMABILITY
------------
Two independent mechanisms, because a multi-hour copy will get interrupted:

  1. `_id` is carried over verbatim. It equals `chunk_id` (see
     legal-engine/pipeline_runner/stage_05_index.py:200-202, which bulk-writes
     with _op_type "index" keyed on chunk_id), so every write is an overwrite,
     never a duplicate. Re-running from scratch is always safe.
  2. Paging is `search_after` on `chunk_id` — a unique keyword field, therefore
     a stable total order — checkpointed to migrate_checkpoint.json after every
     page. A restart picks up where it stopped instead of re-copying 465k docs.
     (`helpers.scan` was not used: scroll cursors cannot be resumed after a
     crash, which is exactly the case that matters here.)

Usage:
    export SRC_PASSWORD='<oracle admin password>'
    export DST_PASSWORD='<gcp admin password>'
    python3 migrate_index.py                 # resumes if a checkpoint exists
    python3 migrate_index.py --restart       # ignore the checkpoint, start over
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from opensearchpy import OpenSearch, helpers

HERE = Path(__file__).resolve().parent
CHECKPOINT = HERE / "migrate_checkpoint.json"
FAILURES = HERE / "migrate_failures.jsonl"

# Source = Oracle (being decommissioned), destination = GCP.
SRC_HOST = os.environ.get("SRC_HOST", "80.225.202.124")
SRC_PORT = int(os.environ.get("SRC_PORT", "9200"))
SRC_USER = os.environ.get("SRC_USER", "admin")
SRC_INDEX = os.environ.get("SRC_INDEX", "case_chunks_v1")

DST_HOST = os.environ.get("DST_HOST", "localhost")
DST_PORT = int(os.environ.get("DST_PORT", "9200"))
DST_USER = os.environ.get("DST_USER", "admin")
DST_INDEX = os.environ.get("DST_INDEX", "case_chunks_v2")

# 500 docs x ~24.9 KB ~= 12.5 MB per fetched page. helpers.bulk then splits that
# into BULK_CHUNK-sized requests, keeping each well under the destination's
# http.max_content_length (measured: 100mb).
PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "500"))
BULK_CHUNK = int(os.environ.get("BULK_CHUNK", "200"))
# Generous: a bulk request that triggers an HNSW merge on a 2-vCPU box can stall
# well past opensearch-py's 10s default.
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "180"))
PROGRESS_EVERY = 10_000

# Sort key. Must be a unique, sortable field for search_after to give a stable
# total order. chunk_id is the doc _id, so uniqueness is guaranteed.
SORT_FIELD = "chunk_id"


def client(host: str, port: int, user: str, password: str) -> OpenSearch:
    """Both clusters run the security plugin with the demo self-signed certs,
    so TLS is on and verification is off — same posture as the app
    (OPENSEARCH_USE_SSL=true / OPENSEARCH_VERIFY_CERTS=false)."""
    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=(user, password),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
        http_compress=True,
        timeout=REQUEST_TIMEOUT,
        max_retries=3,
        retry_on_timeout=True,
    )


def load_checkpoint() -> tuple[list | None, int]:
    if not CHECKPOINT.exists():
        return None, 0
    data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return data.get("search_after"), int(data.get("copied", 0))


def save_checkpoint(search_after: list, copied: int) -> None:
    # Written after the page's bulk has been acknowledged, so a crash re-copies
    # at most one page (harmless — writes are _id-keyed overwrites).
    CHECKPOINT.write_text(
        json.dumps({"search_after": search_after, "copied": copied}), encoding="utf-8"
    )


def fetch_page(src: OpenSearch, search_after: list | None) -> list:
    body: dict = {
        "size": PAGE_SIZE,
        "query": {"match_all": {}},
        "sort": [{SORT_FIELD: "asc"}],
        # No _source filtering: the destination needs chunk_embedding to build
        # its HNSW graph. Dropping it from storage is the mapping's job.
    }
    if search_after:
        body["search_after"] = search_after
    return src.search(index=SRC_INDEX, body=body, request_timeout=REQUEST_TIMEOUT)["hits"]["hits"]


def to_actions(hits: list) -> list:
    return [
        {
            "_op_type": "index",   # full replacement — idempotent by _id
            "_index": DST_INDEX,
            "_id": h["_id"],
            "_source": h["_source"],
        }
        for h in hits
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--restart", action="store_true", help="ignore any checkpoint and start over")
    args = ap.parse_args()

    src_pw = os.environ.get("SRC_PASSWORD")
    dst_pw = os.environ.get("DST_PASSWORD")
    if not src_pw or not dst_pw:
        print("FAIL: set SRC_PASSWORD and DST_PASSWORD in the environment.", file=sys.stderr)
        return 2

    src = client(SRC_HOST, SRC_PORT, SRC_USER, src_pw)
    dst = client(DST_HOST, DST_PORT, DST_USER, dst_pw)

    total = src.count(index=SRC_INDEX)["count"]
    dst_before = dst.count(index=DST_INDEX)["count"]
    print(f"[migrate] source {SRC_HOST}/{SRC_INDEX}: {total:,} docs")
    print(f"[migrate] dest   {DST_HOST}/{DST_INDEX}: {dst_before:,} docs (before)")

    if args.restart and CHECKPOINT.exists():
        CHECKPOINT.unlink()
        print("[migrate] checkpoint discarded (--restart)")

    search_after, copied = load_checkpoint()
    if search_after:
        print(f"[migrate] resuming after {SORT_FIELD}={search_after[0]!r} ({copied:,} already copied)")

    started = time.time()
    failures = 0
    last_report = copied
    copied_this_run = 0   # rate/ETA must not count docs copied by a previous run

    # Overlap the next fetch with the current bulk: the fetch is network-bound
    # against Oracle and the bulk is CPU-bound building HNSW on this box, so
    # running them concurrently is close to free. Same pattern as the thread
    # pools in app/api/routes/search.py.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(fetch_page, src, search_after)
        while True:
            hits = pending.result()
            if not hits:
                break
            next_after = hits[-1]["sort"]
            pending = pool.submit(fetch_page, src, next_after)

            ok, errors = helpers.bulk(
                dst,
                to_actions(hits),
                chunk_size=BULK_CHUNK,
                request_timeout=REQUEST_TIMEOUT,
                raise_on_error=False,
                raise_on_exception=False,
            )
            if errors:
                failures += len(errors)
                with FAILURES.open("a", encoding="utf-8") as fh:
                    for err in errors:
                        fh.write(json.dumps(err) + "\n")

            copied += ok
            copied_this_run += ok
            save_checkpoint(next_after, copied)

            if copied - last_report >= PROGRESS_EVERY:
                elapsed = time.time() - started
                rate = copied_this_run / elapsed if elapsed else 0
                remaining = max(total - copied, 0)
                eta = f"{remaining / rate / 60:.0f}m" if rate else "?"
                pct = 100.0 * copied / total if total else 0
                print(
                    f"[migrate] {copied:,}/{total:,} ({pct:5.1f}%)  "
                    f"{rate:,.0f} docs/s  elapsed {elapsed/60:.1f}m  ETA {eta}  "
                    f"failures {failures}",
                    flush=True,
                )
                last_report = copied

    elapsed = time.time() - started
    print(f"[migrate] finished in {elapsed/60:.1f} minutes ({copied_this_run:,} docs this run)")
    if failures:
        print(f"[migrate] {failures} document failures logged to {FAILURES}", file=sys.stderr)

    # The count is only meaningful after a refresh: the load runs with
    # refresh_interval=-1 (README §5.3), so newly indexed docs are not yet
    # visible to search. Force one before comparing.
    dst.indices.refresh(index=DST_INDEX)
    dst_after = dst.count(index=DST_INDEX)["count"]
    print(f"[migrate] dest {DST_INDEX}: {dst_after:,} docs (source has {total:,})")
    if dst_after != total:
        print(
            f"[migrate] FAIL: count mismatch — dest {dst_after:,} != source {total:,}. "
            f"Re-run to fill gaps (writes are _id-keyed overwrites).",
            file=sys.stderr,
        )
        return 1

    CHECKPOINT.unlink(missing_ok=True)
    print("[migrate] OK: counts match. Next: restore refresh_interval, forcemerge, verify, "
          "then flip the alias (README §5.4-§6.3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
