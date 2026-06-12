"""
Upload case PDFs to the Supabase Storage bucket `case_pdfs`, named `{case_id}.pdf`.

Why this works (Option 1 — name-by-case_id, no DB mapping table):
  - case_id is a stable hash; every pipeline artifact is already keyed by it.
  - output/01_extracted/{case_id}.json carries `source_filename`, the original
    PDF basename (no extension, no year folder).
  - The PDF itself lives at  sample_cases/{year}/{source_filename}.PDF
  - We upload it as  case_pdfs/{case_id}.pdf  so the API can derive the object
    path from case_id directly (PDF_PATH_TEMPLATE = "{case_id}.pdf").

This script lives in client/ but reads the pipeline output + PDFs from the
PARENT repo (one level up from client/). Creds come from client/.env.

Requirements:
    pip install supabase python-dotenv
client/.env must contain (service-role key — uploads bypass RLS):
    SUPABASE_URL=...
    SUPABASE_SERVICE_ROLE_KEY=...

Usage (from client/):
    python scripts/upload_pdfs_to_supabase.py --dry-run     # report coverage, upload nothing
    python scripts/upload_pdfs_to_supabase.py               # upload all
    python scripts/upload_pdfs_to_supabase.py --limit 20    # try a small batch first
    python scripts/upload_pdfs_to_supabase.py --skip-existing
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

CLIENT_ROOT = Path(__file__).resolve().parents[1]   # client/
DATA_ROOT = Path(__file__).resolve().parents[2]     # repo root (parent of client/)
EXTRACTED_DIR = DATA_ROOT / "output" / "01_extracted"
SAMPLE_DIR = DATA_ROOT / "sample_cases"
BUCKET = "case_pdfs"

load_dotenv(CLIENT_ROOT / ".env")


def find_pdf(source_filename: str) -> Path | None:
    """Locate sample_cases/*/<source_filename>.<pdf> across year folders."""
    pattern = f"*/{glob.escape(source_filename)}.*"
    for match in SAMPLE_DIR.glob(pattern):
        if match.suffix.lower() == ".pdf":
            return match
    return None


def build_pairs(limit: int | None) -> tuple[list[tuple[str, Path]], list[str]]:
    """Return (uploadable [(case_id, pdf_path)], unresolved [case_id])."""
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
        pdf = find_pdf(source_filename)
        if pdf is None:
            print(f"⚠️  {case_id}: PDF not found for '{source_filename}'")
            unresolved.append(case_id)
            continue
        pairs.append((case_id, pdf))
    return pairs, unresolved


def existing_object_names(client) -> set[str]:
    """Paginate the bucket listing so --skip-existing works on large buckets."""
    names: set[str] = set()
    offset, page = 0, 1000
    while True:
        batch = client.storage.from_(BUCKET).list(
            options={"limit": page, "offset": offset}
        )
        if not batch:
            break
        names.update(obj["name"] for obj in batch)
        if len(batch) < page:
            break
        offset += page
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report coverage, upload nothing")
    ap.add_argument("--workers", type=int, default=8, help="concurrent uploads (default 8)")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N cases")
    ap.add_argument("--skip-existing", action="store_true", help="skip objects already in the bucket")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        sys.exit("❌ Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in client/.env")
    if not EXTRACTED_DIR.is_dir():
        sys.exit(f"❌ Missing {EXTRACTED_DIR}")

    try:
        from supabase import create_client
    except ImportError:
        sys.exit("❌ supabase not installed — run: pip install supabase python-dotenv")

    pairs, unresolved = build_pairs(args.limit)
    print(f"\n📂 {len(pairs)} PDFs resolved, {len(unresolved)} unresolved.")

    if args.dry_run:
        print("(dry run — nothing uploaded)")
        return 0
    if not pairs:
        return 0

    client = create_client(url, key)

    if args.skip_existing:
        have = existing_object_names(client)
        before = len(pairs)
        pairs = [(c, p) for c, p in pairs if f"{c}.pdf" not in have]
        print(f"⏭️  skipping {before - len(pairs)} already in bucket; {len(pairs)} to upload")

    def upload(case_id: str, pdf: Path) -> str:
        client.storage.from_(BUCKET).upload(
            f"{case_id}.pdf",
            pdf.read_bytes(),
            {"content-type": "application/pdf", "upsert": "true"},
        )
        return case_id

    ok = err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(upload, c, p): c for c, p in pairs}
        for fut in as_completed(futs):
            try:
                fut.result()
                ok += 1
                if ok % 100 == 0:
                    print(f"  …{ok} uploaded")
            except Exception as e:
                err += 1
                print(f"❌ {futs[fut]}: {e}")

    print(f"\n✅ done: {ok} uploaded, {err} failed, {len(unresolved)} unresolved")
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
