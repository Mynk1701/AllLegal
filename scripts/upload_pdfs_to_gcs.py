"""
Upload case PDFs to the GCS bucket, named `{case_id}.pdf`.

Companion to upload_pdfs_to_supabase.py — same discovery/matching logic
(Option 1 — name-by-case_id, no DB mapping table), retargeted at Google
Cloud Storage because Supabase's free/current tier (5GB) is smaller than
the ~11GB corpus. See HANDOVER.md and the project_opensearch_gcp_migration
memory for why this move is happening.

Auth: GCS HMAC interoperability keys (GCS_HMAC_ACCESS_KEY / GCS_HMAC_SECRET_KEY),
not a service-account JSON key — an org policy on this project
(iam.disableServiceAccountKeyCreation) blocks both service-account keys and
service-account HMAC keys; a user-account HMAC key (Cloud Storage → Settings →
Interoperability → "Access keys for your user account") isn't covered by that
constraint. GCS's XML API is S3-compatible, so boto3 talks to it directly via
the endpoint_url override below — no google-cloud-storage SDK needed.

Requirements:
    pip install boto3 tqdm python-dotenv
client/.env must contain:
    GCS_BUCKET=...
    GCS_HMAC_ACCESS_KEY=...
    GCS_HMAC_SECRET_KEY=...

Usage (from client/):
    python scripts/upload_pdfs_to_gcs.py --dry-run     # report coverage, upload nothing
    python scripts/upload_pdfs_to_gcs.py               # upload all
    python scripts/upload_pdfs_to_gcs.py --limit 20    # try a small batch first
    python scripts/upload_pdfs_to_gcs.py --skip-existing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

CLIENT_ROOT = Path(__file__).resolve().parents[1]   # client/
DATA_ROOT = Path(__file__).resolve().parents[2]     # repo root (parent of client/)
EXTRACTED_DIR = DATA_ROOT / "output" / "01_extracted"
# NOTE: must track pipeline_runner/stage_01_extract.py's PDF_INPUT_DIR.
PDF_INPUT_DIR = DATA_ROOT / "supreme_court_judgements" / "supreme_court_judgments"
GCS_ENDPOINT = "https://storage.googleapis.com"

load_dotenv(CLIENT_ROOT / ".env")


def _discover_pdfs() -> dict[str, Path]:
    """{filename_stem: path} for every PDF under PDF_INPUT_DIR (recursive)."""
    found: dict[str, Path] = {}
    for pat in ("**/*.pdf", "**/*.PDF"):
        for p in PDF_INPUT_DIR.glob(pat):
            found.setdefault(p.stem, p)
    return found


def build_pairs(limit: int | None) -> tuple[list[tuple[str, Path]], list[str]]:
    """Return (uploadable [(case_id, pdf_path)], unresolved [case_id])."""
    pdfs_by_stem = _discover_pdfs()
    pairs: list[tuple[str, Path]] = []
    unresolved: list[str] = []
    files = sorted(EXTRACTED_DIR.glob("*.json"))
    if limit:
        files = files[:limit]
    for jf in files:
        case_id = jf.stem
        try:
            source_filename = json.loads(jf.read_text()).get("source_filename")
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  {case_id}: could not read extracted JSON ({e})")
            unresolved.append(case_id)
            continue
        if not source_filename:
            print(f"⚠️  {case_id}: no source_filename in extracted JSON")
            unresolved.append(case_id)
            continue
        pdf = pdfs_by_stem.get(source_filename)
        if pdf is None:
            print(f"⚠️  {case_id}: PDF not found for '{source_filename}'")
            unresolved.append(case_id)
            continue
        pairs.append((case_id, pdf))
    return pairs, unresolved


def existing_object_names(client, bucket: str) -> set[str]:
    """Paginate the bucket listing so --skip-existing works on large buckets."""
    names: set[str] = set()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            names.add(obj["Key"])
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report coverage, upload nothing")
    ap.add_argument("--workers", type=int, default=8, help="concurrent uploads (default 8)")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N cases")
    ap.add_argument("--skip-existing", action="store_true", help="skip objects already in the bucket")
    args = ap.parse_args()

    bucket = os.environ.get("GCS_BUCKET")
    access_key = os.environ.get("GCS_HMAC_ACCESS_KEY")
    secret_key = os.environ.get("GCS_HMAC_SECRET_KEY")
    if not bucket or not access_key or not secret_key:
        sys.exit("❌ Set GCS_BUCKET, GCS_HMAC_ACCESS_KEY and GCS_HMAC_SECRET_KEY in client/.env")
    if not EXTRACTED_DIR.is_dir():
        sys.exit(f"❌ Missing {EXTRACTED_DIR}")

    try:
        import boto3
    except ImportError:
        sys.exit("❌ boto3 not installed — run: pip install boto3 tqdm")

    pairs, unresolved = build_pairs(args.limit)
    print(f"\n📂 {len(pairs)} PDFs resolved, {len(unresolved)} unresolved.")

    if args.dry_run:
        print("(dry run — nothing uploaded)")
        return 0
    if not pairs:
        return 0

    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=GCS_ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        # botocore >=1.36 defaults to attaching an AWS-specific flexible
        # checksum on PutObject, which GCS's S3-compatible XML API doesn't
        # recognize the same way -> SignatureDoesNotMatch. Restore the old
        # "only when required" behavior so the signature matches.
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )

    if args.skip_existing:
        have = existing_object_names(client, bucket)
        before = len(pairs)
        pairs = [(c, p) for c, p in pairs if f"{c}.pdf" not in have]
        print(f"⏭️  skipping {before - len(pairs)} already in bucket; {len(pairs)} to upload")

    def upload(case_id: str, pdf: Path) -> int:
        data = pdf.read_bytes()
        client.put_object(
            Bucket=bucket,
            Key=f"{case_id}.pdf",
            Body=data,
            ContentType="application/pdf",
        )
        return len(data)

    from tqdm import tqdm

    ok = err = 0
    uploaded_bytes = 0
    bar = tqdm(total=len(pairs), unit="pdf", dynamic_ncols=True, desc="uploading")
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(upload, c, p): c for c, p in pairs}
        for fut in as_completed(futs):
            try:
                uploaded_bytes += fut.result()
                ok += 1
            except Exception as e:
                err += 1
                bar.write(f"❌ {futs[fut]}: {e}")
            bar.update(1)
            bar.set_postfix(ok=ok, failed=err, mb=f"{uploaded_bytes / 1e6:.1f}")
    bar.close()

    print(f"\n✅ done: {ok} uploaded ({uploaded_bytes / 1e6:.1f} MB), {err} failed, {len(unresolved)} unresolved")
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
