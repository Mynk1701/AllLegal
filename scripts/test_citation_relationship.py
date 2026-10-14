"""
Feasibility test: can an LLM classify citation TREATMENT (followed / distinguished /
overruled / cited) from the chunk text around a citation_graph edge?

`citation_graph.relationship` only ever holds the literal string "cited" today
(53,045 rows, zero variation) — this script is NOT the production backfill for
that column. It samples a small number of real edges, builds each one's context
(the tagged chunk plus a window of neighbouring chunks — the actual treatment
language often sits a few paragraphs away from where the citation was tagged,
confirmed by hand on a real case before writing this script), classifies with
Haiku 4.5 and Sonnet 5, and writes a human-reviewable report so a person can
judge whether this approach is worth building into a real pipeline.

Design: plans/read-alllegal-drafting-module-track-spec-keen-ladybug.md,
section "Feasibility script — citation treatment classification".

Usage (from repo root, with the `legal-helper` conda env's python):
    python scripts/test_citation_relationship.py --dry-run
    python scripts/test_citation_relationship.py
    python scripts/test_citation_relationship.py --limit 10 --models haiku
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))  # repo root, for `app.*` imports

from app.services.supabase import supabase_service  # noqa: E402
from app.services.opensearch_service import opensearch_service  # noqa: E402
from app.services import case_index  # noqa: E402

# .env must be loaded explicitly for ANTHROPIC_API_KEY — app.core.config.settings
# doesn't declare that field (extra="ignore" silently drops anything it doesn't
# know about), so importing the app services above does NOT put it into
# os.environ. Mirrors the pattern in law helper/src/scripts/batch_test_metadata.py.
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass


MODEL_IDS = {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-5"}
# $ per 1M tokens (input, output) — confirmed current as of this script's authoring.
# Re-verify against the Anthropic console before relying on this beyond a small
# feasibility run; prices change.
MODEL_PRICING = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
}

Treatment = Literal["followed", "cautionary", "overruled", "neutral"]
TREATMENT_LABELS = {
    "followed": "Followed",
    "cautionary": "Distinguished",
    "overruled": "Overruled",
    "neutral": "Cited",
}


class TreatmentClassification(BaseModel):
    treatment: Treatment
    confidence: Literal["high", "medium", "low"]
    justification: str


SYSTEM_PROMPT = """You are a legal-research assistant analysing an Indian court judgment to
determine how it treated one earlier precedent it cites.

You are given a contiguous window of text chunks from the CITING judgment, in original
document order, each labeled with its chunk_type and chunk_sequence. Exactly one chunk is
marked TAGGED — our citation-graph metadata recorded that chunk as containing the citation to
the precedent named below. Indian judgments often quote/paraphrase a precedent in one chunk
type (observed: "Precedent") while stating the court's actual verdict on it nearby in a
DIFFERENT chunk type (observed: "Ratio of the decision", "Ruling by Present Court") — so read
the WHOLE window, not just the tagged chunk, before deciding.

Classify the treatment as exactly one of:
- followed ("Followed"): the citing court applies/relies on the precedent's ratio as binding or
  persuasive authority for its own decision, without disagreement.
- cautionary ("Distinguished"): the citing court engages with the precedent but limits,
  distinguishes, doubts, or qualifies its applicability to the present facts, without rejecting
  it outright.
- overruled ("Overruled"): the citing court expressly disagrees with, overrules, or declines to
  follow the precedent's ratio.
- neutral ("Cited"): mentioned only in passing (e.g. in a list of authorities, as background) —
  the window does not contain a clear treatment signal either way.

Do NOT default to "neutral" merely out of caution if a clear signal exists anywhere in the
window — "neutral" should mean the signal is genuinely absent, not that you are unsure which of
the other three applies. If genuinely torn between two labels, pick the better-supported one and
set confidence to "low" or "medium", explaining the ambiguity in justification."""

USER_TEMPLATE = """Citing case: {case_name} ({court}, {date_decided})
Precedent being classified: "{raw_cited_canonical_key}"{resolved_name_note}

Context window (chunk_sequence {lo}-{hi}; TAGGED = chunk_sequence {tagged_sequence}):

{rendered_chunks}

Classify how THIS citing case treated the precedent named above."""


def _derive_case_id(canonical_key: str) -> str:
    """Mirrors app/api/routes/cases.py's _derive_case_id — resolves a
    cited_canonical_key to the cited case's case_id, if it's in our corpus."""
    return hashlib.sha256(" ".join(canonical_key.split()).lower().encode("utf-8")).hexdigest()[:10]


# ==================== Sampling ====================

def count_indexed_cases(limit: int = 30000) -> int:
    """Distinct case_ids with at least one chunk in whichever OpenSearch
    index/cluster is currently configured (local docker-compose or, via the
    SSH tunnel, the full GCP cluster) — informational only, not used to
    filter the citation_graph query below (see fetch_all_citation_rows)."""
    resp = opensearch_service.client.search(
        index=opensearch_service.index,
        body={"size": 0, "aggs": {"cases": {"cardinality": {"field": "case_id"}}}},
    )
    return resp["aggregations"]["cases"]["value"]


def fetch_all_citation_rows(*, page_request: int = 1000) -> dict[str, list[dict]]:
    """All citation_graph rows, grouped by citing_case_id.

    No case_id filter: an `.in_()` call against a large case_id list doesn't
    avoid needing pagination (PostgREST still caps each response), and risks
    an oversized query string once the candidate pool is tens of thousands
    of case_ids (as it now is against the full corpus). Plain pagination
    over the whole table is simpler and correct at any corpus size; a case
    whose chunks turn out not to be in the currently-configured index is
    caught later by build_context_window() returning None and skipped
    there, same as any other data-quality gap.

    `page_request` is what we ASK for per page — this project's PostgREST
    instance silently caps each response at its own server-side max-rows
    (confirmed empirically: exactly 999, not the 1000 one might expect), so
    pagination must advance by the ACTUAL row count returned, not by
    `page_request`, and must stop only on a genuinely empty page (`== 0`),
    never on `< page_request` — the latter would stop after page 1 forever,
    since every non-final page comes back short of what was asked for.
    `.order()` on every selected column keeps `.range()` deterministic and
    non-overlapping across calls (undefined otherwise per the SQL standard)."""
    all_rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            supabase_service.admin.table("citation_graph")
            .select("citing_case_id, cited_canonical_key, chunk_id")
            .order("citing_case_id").order("chunk_id").order("cited_canonical_key")
            .range(offset, offset + page_request - 1)
            .execute()
        )
        page = resp.data or []
        all_rows.extend(page)
        if len(page) == 0:
            break
        offset += len(page)
    by_case: dict[str, list[dict]] = {}
    for row in all_rows:
        by_case.setdefault(row["citing_case_id"], []).append(row)
    return by_case


@dataclass
class SampledEdge:
    citing_case_id: str
    cited_canonical_key: str
    chunk_id: str


def sample_edges(
    by_case: dict[str, list[dict]],
    *,
    limit: int,
    min_cases: int,
    max_per_case: int,
    seed: int,
    oversample: int = 10,
) -> list[SampledEdge]:
    """Stratified round-robin sample across citing cases (not top-N by row
    count), deduped per case by cited_canonical_key. Oversamples by a few
    edges so a later data-quality skip (tagged chunk not found in the index)
    doesn't silently shrink the final processed sample below `limit`."""
    rng = random.Random(seed)
    target = limit + oversample

    deduped: dict[str, list[dict]] = {}
    for cid, rows in by_case.items():
        by_key: dict[str, dict] = {}
        for r in rows:
            key = r.get("cited_canonical_key")
            if key and key not in by_key:
                by_key[key] = r
        if by_key:
            deduped[cid] = list(by_key.values())

    eligible = list(deduped.keys())
    rng.shuffle(eligible)
    for rows in deduped.values():
        rng.shuffle(rows)

    sample: list[SampledEdge] = []
    taken_per_case = {cid: 0 for cid in eligible}
    changed = True
    while len(sample) < target and changed:
        changed = False
        for cid in eligible:
            if len(sample) >= target:
                break
            rows = deduped[cid]
            if taken_per_case[cid] >= max_per_case or taken_per_case[cid] >= len(rows):
                continue
            row = rows[taken_per_case[cid]]
            sample.append(SampledEdge(
                citing_case_id=cid,
                cited_canonical_key=row["cited_canonical_key"],
                chunk_id=row["chunk_id"],
            ))
            taken_per_case[cid] += 1
            changed = True

    distinct_cases = len({e.citing_case_id for e in sample})
    if distinct_cases < min_cases:
        print(f"⚠️  Sample spans only {distinct_cases} distinct citing cases (wanted >= {min_cases}) "
              f"— corpus may just be small locally. Proceeding anyway.")

    return sample


# ==================== Context window ====================

@dataclass
class WindowChunk:
    chunk_id: str
    chunk_type: Optional[str]
    chunk_sequence: int
    chunk_text: str
    tagged: bool


@dataclass
class ContextWindow:
    chunks: list[WindowChunk]
    tagged_sequence: int
    lo: int
    hi: int


_case_chunks_cache: dict[str, list[dict]] = {}


def fetch_case_chunks_cached(case_id: str) -> list[dict]:
    """Memoized get_case_chunks() — multiple sampled edges often share a
    citing_case_id, and a case has at most a couple hundred chunks, so
    fetching-all-then-filtering is fine at this scale (no range-filter
    method exists on opensearch_service to do better)."""
    if case_id not in _case_chunks_cache:
        hits = opensearch_service.get_case_chunks(case_id)
        _case_chunks_cache[case_id] = sorted(
            (h["_source"] for h in hits), key=lambda s: s.get("chunk_sequence") or 0
        )
    return _case_chunks_cache[case_id]


def build_context_window(
    case_id: str, tagged_chunk_id: str, window: int, exclude_types: frozenset[str] = frozenset()
) -> Optional[ContextWindow]:
    """`exclude_types` drops chunks of those chunk_type values from the
    window UNLESS they're the tagged chunk itself (always kept regardless
    of type) — validated against the two prior real runs: at window=4,
    excluding {"Facts","Statute"} cuts window token volume to ~53% of the
    original ±8/no-filter window with zero measured loss in how often a
    Ratio-of-the-decision/Ruling-by-Present-Court chunk is still present."""
    chunks = fetch_case_chunks_cached(case_id)
    tagged = next((c for c in chunks if c.get("chunk_id") == tagged_chunk_id), None)
    if tagged is None:
        return None
    seq0 = tagged.get("chunk_sequence") or 0
    lo, hi = seq0 - window, seq0 + window
    windowed = [
        WindowChunk(
            chunk_id=c.get("chunk_id", ""),
            chunk_type=c.get("chunk_type"),
            chunk_sequence=c.get("chunk_sequence") or 0,
            chunk_text=c.get("chunk_text") or "",
            tagged=(c.get("chunk_id") == tagged_chunk_id),
        )
        for c in chunks
        if lo <= (c.get("chunk_sequence") or 0) <= hi
        and (c.get("chunk_id") == tagged_chunk_id or c.get("chunk_type") not in exclude_types)
    ]
    return ContextWindow(chunks=windowed, tagged_sequence=seq0, lo=lo, hi=hi)


def render_window_text(window: ContextWindow) -> str:
    lines = []
    for c in window.chunks:
        tag = "  <<< TAGGED" if c.tagged else ""
        lines.append(f"[{c.chunk_type or 'Unknown'}] (seq {c.chunk_sequence}){tag}:\n{c.chunk_text}\n")
    return "\n".join(lines)


# ==================== Precedent / case name resolution ====================

def resolve_cited_name(cited_canonical_key: str) -> tuple[Optional[str], Optional[str]]:
    """Mirrors the resolution chain in app/api/routes/cases.py: uploaded
    subset (has case_name) -> full ~26k case_index -> unresolved."""
    rid = _derive_case_id(cited_canonical_key)
    hit = supabase_service.get_cases_by_ids([rid]).get(rid)
    if hit:
        return rid, hit.get("case_name")
    if case_index.known(rid):
        return rid, case_index.name_of(rid)
    return rid, None


def resolve_case_meta(case_id: str) -> dict:
    row = supabase_service.get_case_by_id(case_id) or {}
    return {
        "case_name": row.get("case_name") or case_index.name_of(case_id) or case_id,
        "court": row.get("court"),
        "date_decided": row.get("date_decided"),
    }


def build_prompt(edge: SampledEdge, case_meta: dict, cited_name: Optional[str], window: ContextWindow) -> str:
    resolved_note = f" (resolved: {cited_name})" if cited_name else " (not resolved to a case name in our corpus)"
    return USER_TEMPLATE.format(
        case_name=case_meta["case_name"],
        court=case_meta.get("court") or "unknown court",
        date_decided=case_meta.get("date_decided") or "unknown date",
        raw_cited_canonical_key=edge.cited_canonical_key,
        resolved_name_note=resolved_note,
        lo=window.lo, hi=window.hi, tagged_sequence=window.tagged_sequence,
        rendered_chunks=render_window_text(window),
    )


# ==================== Anthropic calls ====================

def model_call_kwargs(alias: str) -> dict:
    """Sonnet 5 rejects temperature/top_p/top_k (400) and uses an `effort`
    ladder instead; Haiku 4.5 doesn't document effort/thinking support at
    all, so it gets no extra config."""
    if alias == "sonnet":
        return {"output_config": {"effort": "low"}}
    return {}


def call_cost(model_id: str, usage) -> float:
    in_price, out_price = MODEL_PRICING[model_id]
    return usage.input_tokens / 1_000_000 * in_price + usage.output_tokens / 1_000_000 * out_price


def classify(client, alias: str, user_content: str):
    model_id = MODEL_IDS[alias]
    response = client.messages.parse(
        model=model_id,
        max_tokens=1024 if alias == "haiku" else 2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        output_format=TreatmentClassification,
        **model_call_kwargs(alias),
    )
    return response.parsed_output, response.usage


# ==================== Report rendering ====================

REVIEWER_GUIDANCE = """## How to judge feasibility

Don't just look at raw agreement. Judge on:

1. **Label diversity** — do the models actually use all 4 labels, or collapse almost
   everything to `neutral`/`followed`? Never seeing `cautionary`/`overruled` may mean the
   model is under-discriminating, not that this sample truly lacks those cases.
2. **Haiku vs Sonnet agreement** — high agreement is the strongest "go cheap" signal for a
   real backfill. Disagreement concentrated on `cautionary`/`overruled` specifically (the
   harder, rarer labels) is the strongest reason to pay for Sonnet instead.
3. **Agreement with your own manual read of the window** — the one real ground truth
   available at this scale. Fill in "Your verdict" below for each edge.
4. **Whether the window actually mattered** — for a few edges, re-read just the TAGGED
   chunk alone vs. the full window. If the answer would have been the same either way, the
   window isn't earning its extra cost for that edge; if it flips the answer, that's the
   exact failure mode this design was built to catch.
"""


def render_markdown_report(run_config: dict, results: list[dict], total_cost: float) -> str:
    lines: list[str] = []
    lines.append("# Citation treatment classification — feasibility report")
    lines.append("")
    excl = ','.join(run_config.get('exclude_types') or []) or 'none'
    lines.append(
        f"Run: {run_config['timestamp']} · limit={run_config['limit']} · "
        f"window=±{run_config['window']} · exclude_types={excl} · "
        f"models={', '.join(run_config['models'])} · seed={run_config['seed']}"
    )
    distinct_cases = len({r["citing_case_id"] for r in results})
    lines.append(
        f"Edges classified: {len(results)} · distinct citing cases: {distinct_cases} · "
        f"total cost: ${total_cost:.4f}"
    )
    lines.append("")
    lines.append(REVIEWER_GUIDANCE)
    lines.append("## Summary")
    lines.append("")
    header = (
        "| # | Citing case | Cited precedent | "
        + " | ".join(m.capitalize() for m in run_config["models"])
        + " | Agree? |"
    )
    sep = "|---" * (3 + len(run_config["models"]) + 1) + "|"
    lines.append(header)
    lines.append(sep)
    for r in results:
        cited_label = r["cited_case_name_resolved"] or r["cited_canonical_key"][:40]
        cells = []
        labels_seen = set()
        for m in run_config["models"]:
            cl = r["classifications"].get(m, {})
            t = cl.get("treatment", "ERROR" if "error" in cl else "—")
            labels_seen.add(t)
            cells.append(TREATMENT_LABELS.get(t, t))
        agree = "✅" if len(labels_seen) == 1 else "❌"
        lines.append(
            f"| {r['edge_index'] + 1} | {r['citing_case_name'][:30]} | {cited_label[:30]} | "
            + " | ".join(cells)
            + f" | {agree} |"
        )
    lines.append("")

    for r in results:
        lines.append(
            f"## Edge {r['edge_index'] + 1}: {r['citing_case_name']} citing "
            f"{r['cited_case_name_resolved'] or r['cited_canonical_key']}"
        )
        lines.append("")
        lines.append(f"- Cited key (raw): `{r['cited_canonical_key']}`")
        lines.append(f"- Tagged chunk: `{r['chunk_id']}` (chunk_sequence {r['tagged_chunk_sequence']})")
        lines.append(f"- Window: chunk_sequence {r['window']['lo']}–{r['window']['hi']}")
        lines.append("")
        lines.append("<details><summary>Context window given to the model</summary>")
        lines.append("")
        lines.append("```")
        for c in r["window"]["chunks"]:
            tag = "  <<< TAGGED" if c["tagged"] else ""
            lines.append(f"[{c['chunk_type'] or 'Unknown'}] (seq {c['chunk_sequence']}){tag}:")
            lines.append(c["chunk_text"])
            lines.append("")
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")
        for m in run_config["models"]:
            cl = r["classifications"].get(m)
            if not cl:
                continue
            if "error" in cl:
                lines.append(f"**{m.capitalize()}**: ERROR — {cl['error']}")
            else:
                lines.append(
                    f"**{m.capitalize()}**: `{cl['treatment']}` ({TREATMENT_LABELS[cl['treatment']]}), "
                    f"confidence={cl['confidence']}, cost=${cl['cost_usd']:.4f}"
                )
                lines.append(f"> {cl['justification']}")
            lines.append("")
        lines.append("### Your verdict")
        lines.append("- [ ] followed   - [ ] cautionary   - [ ] overruled   - [ ] neutral")
        lines.append("- Notes: ")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


# ==================== Dry run ====================

def run_dry_run(prepared: list[dict], models: list[str]) -> int:
    import anthropic

    client = anthropic.Anthropic()
    print(f"\n🧪 DRY RUN — counting tokens for {len(prepared)} edges x {len(models)} models (zero cost)...\n")
    total_est_cost = 0.0
    for i, p in enumerate(prepared):
        prompt = build_prompt(p["edge"], p["case_meta"], p["cited_name"], p["window"])
        for alias in models:
            model_id = MODEL_IDS[alias]
            try:
                count = client.messages.count_tokens(
                    model=model_id, system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as e:
                print(f"❌ count_tokens failed for {alias}: {e}", file=sys.stderr)
                continue
            in_price, out_price = MODEL_PRICING[model_id]
            # Output is unknown pre-generation; assume ~150 tokens (label + confidence + short justification).
            est_cost = count.input_tokens / 1_000_000 * in_price + 150 / 1_000_000 * out_price
            total_est_cost += est_cost
            print(f"[{i + 1}/{len(prepared)}] {alias:<6} input_tokens={count.input_tokens:<6} est_cost=${est_cost:.4f}")
    print(f"\n💰 Estimated total cost for a real run: ${total_est_cost:.4f} (output assumed ~150 tokens/call)")
    print("   No API generation calls were made. No files written.")
    return 0


# ==================== CLI / main ====================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Feasibility test: classify citation treatment (followed/distinguished/"
                    "overruled/cited) for a small sample of real citation_graph edges."
    )
    parser.add_argument("--limit", type=int, default=25, help="Number of citation edges to classify (default: 25)")
    parser.add_argument("--window", type=int, default=8, help="chunk_sequence +/- window around the tagged chunk (default: 8)")
    parser.add_argument(
        "--exclude-types", default="",
        help="Comma list of chunk_type values to drop from the window (tagged chunk is always kept "
             "regardless of its type), e.g. 'Facts,Statute' — validated at --window 4 to cut window "
             "token volume ~47%% with zero measured loss in Ratio-chunk coverage (default: none)",
    )
    parser.add_argument("--models", default="haiku,sonnet", help="Comma list from {haiku,sonnet} (default: haiku,sonnet)")
    parser.add_argument("--min-cases", type=int, default=8, help="Warn if the sample spans fewer distinct citing cases than this (default: 8)")
    parser.add_argument("--max-edges-per-case", type=int, default=3, help="Cap on edges drawn from one citing case (default: 3)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducible sampling (default: 42)")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "scripts" / "output" / "citation_relationship_test")
    parser.add_argument("--dry-run", action="store_true", help="Build windows + count tokens only; no API calls, no files written")
    parser.add_argument("--max-calls", type=int, default=120, help="Hard refusal above this many total LLM calls without --force (default: 120)")
    parser.add_argument("--force", action="store_true", help="Override --max-calls")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    for m in models:
        if m not in MODEL_IDS:
            print(f"❌ Unknown model alias '{m}'. Choose from: {', '.join(MODEL_IDS)}", file=sys.stderr)
            return 1
    if not models:
        print("❌ --models resolved to an empty list.", file=sys.stderr)
        return 1

    total_calls = args.limit * len(models)
    if total_calls > args.max_calls and not args.force:
        print(
            f"❌ Requested {total_calls} LLM calls ({args.limit} edges x {len(models)} models) "
            f"exceeds --max-calls={args.max_calls}. This script is a small feasibility test, "
            f"not the production backfill — pass --force to override.",
            file=sys.stderr,
        )
        return 1

    print("🔍 Checking the configured OpenSearch index...")
    indexed_case_count = count_indexed_cases()
    print(f"   {indexed_case_count} distinct case_ids have chunks in the current index.")

    print("🔍 Fetching all citation_graph rows (paginated)...")
    by_case = fetch_all_citation_rows()
    print(
        f"   {len(by_case)} distinct citing cases have >=1 citation_graph row "
        f"({sum(len(v) for v in by_case.values())} rows total)."
    )
    if not by_case:
        print("❌ No citation_graph rows found. Is Supabase reachable?", file=sys.stderr)
        return 1

    candidates = sample_edges(
        by_case, limit=args.limit, min_cases=args.min_cases,
        max_per_case=args.max_edges_per_case, seed=args.seed,
    )
    print(
        f"📋 Sampled {len(candidates)} candidate edges across "
        f"{len({e.citing_case_id for e in candidates})} distinct citing cases."
    )

    exclude_types = frozenset(t.strip() for t in args.exclude_types.split(",") if t.strip())

    prepared = []
    for edge in candidates:
        if len(prepared) >= args.limit:
            break
        window = build_context_window(edge.citing_case_id, edge.chunk_id, args.window, exclude_types)
        if window is None:
            print(f"⚠️  Skipping edge: tagged chunk {edge.chunk_id} not found in {edge.citing_case_id}'s indexed chunks.")
            continue
        case_meta = resolve_case_meta(edge.citing_case_id)
        cited_case_id, cited_name = resolve_cited_name(edge.cited_canonical_key)
        prepared.append({
            "edge": edge, "window": window, "case_meta": case_meta,
            "cited_case_id": cited_case_id, "cited_name": cited_name,
        })

    if len(prepared) < args.limit:
        print(
            f"⚠️  Only prepared {len(prepared)}/{args.limit} edges (ran out of oversampled "
            f"candidates after data-quality skips). Proceeding with what's available."
        )
    if not prepared:
        print("❌ No edges could be prepared (every candidate's tagged chunk was missing from the index).", file=sys.stderr)
        return 1

    if args.dry_run:
        return run_dry_run(prepared, models)

    import anthropic

    client = anthropic.Anthropic()

    results: list[dict] = []
    total_cost = 0.0
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.output_dir / run_timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.json"
    report_path = out_dir / "report.md"

    run_config = {
        "limit": args.limit, "window": args.window, "models": models,
        "exclude_types": sorted(exclude_types),
        "seed": args.seed, "timestamp": run_timestamp,
        "model_ids": {m: MODEL_IDS[m] for m in models},
    }

    def flush() -> None:
        payload = {"run_config": run_config, "edges": results, "total_cost_usd": round(total_cost, 6)}
        results_path.write_text(json.dumps(payload, indent=2, default=str))
        report_path.write_text(render_markdown_report(run_config, results, total_cost))

    print(f"\n🚀 Classifying {len(prepared)} edges x {len(models)} models ({len(prepared) * len(models)} calls)...\n")
    try:
        for i, p in enumerate(prepared):
            edge, window, case_meta = p["edge"], p["window"], p["case_meta"]
            prompt = build_prompt(edge, case_meta, p["cited_name"], window)
            record = {
                "edge_index": i,
                "citing_case_id": edge.citing_case_id,
                "citing_case_name": case_meta["case_name"],
                "cited_canonical_key": edge.cited_canonical_key,
                "cited_case_id_resolved": p["cited_case_id"],
                "cited_case_name_resolved": p["cited_name"],
                "chunk_id": edge.chunk_id,
                "tagged_chunk_sequence": window.tagged_sequence,
                "window": {"lo": window.lo, "hi": window.hi, "chunks": [asdict(c) for c in window.chunks]},
                "classifications": {},
                "human_verdict": None,
            }
            for alias in models:
                try:
                    parsed, usage = classify(client, alias, prompt)
                except Exception as e:
                    print(f"❌ [{i + 1}/{len(prepared)}] {alias} call failed: {e}", file=sys.stderr)
                    record["classifications"][alias] = {"error": str(e)}
                    continue
                cost = call_cost(MODEL_IDS[alias], usage)
                total_cost += cost
                record["classifications"][alias] = {
                    "treatment": parsed.treatment, "confidence": parsed.confidence,
                    "justification": parsed.justification,
                    "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
                    "cost_usd": round(cost, 6),
                }
                print(
                    f"[{i + 1}/{len(prepared)}] {alias:<6} edge={edge.citing_case_id}->"
                    f"{edge.cited_canonical_key[:40]!r} treatment={parsed.treatment:<10} "
                    f"cost=${cost:.4f} running_total=${total_cost:.4f}"
                )
            results.append(record)
            flush()
    finally:
        flush()

    print(f"\n✅ Done. {len(results)} edges classified. Total cost: ${total_cost:.4f}")
    print(f"   JSON:     {results_path}")
    print(f"   Markdown: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
