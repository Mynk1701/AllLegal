"""
Renders one track document (a `.docx`) from a matter's facts.

Needs `docxtpl` + `python-docx` (see requirements.txt) — imported lazily so
the rest of app.drafting (models, registry, deadlines, validation) stays
importable even in an environment where those haven't been installed yet
(e.g. this module isn't exercised by the pure unit tests in tests/drafting/).

Design (LLD S.7):
  - Templates are `.docx` files with Jinja tags (docxtpl), so a lawyer edits
    wording in Word without a code deploy.
  - A required leaf field that's missing renders as a highlighted
    "[●  label  ●]" marker rather than silently vanishing, and is also
    listed in the returned `gaps`.
  - Output carries a "DRAFT — FOR ADVOCATE REVIEW" banner until finalised.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.drafting.deadlines.adapters import to_deadline_facts
from app.drafting.deadlines.engine import DeadlineResult, compute as compute_deadlines
from app.drafting.models.cheque_bounce import ChequeBounceFacts
from app.drafting.registry import DocumentConfig, TrackConfig
from app.drafting.render.formatters import amount_in_words, format_date_long

TEMPLATES_DIR = Path(__file__).parent.parent / "tracks" / "cheque_bounce" / "templates"

MISSING_MARKER = "[●  {label}  ●]"


class TemplateRenderError(RuntimeError):
    pass


class DocumentNotApplicableError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderResult:
    content: bytes
    gaps: List[str]
    facts_hash: str
    template_version: str


def _get(obj: Any, path: str) -> Any:
    """Dotted-path getter over the facts dict (e.g. 'notice.delivered_on').
    A missing/None leaf returns None; this never raises on an absent key."""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.get(part) if isinstance(cur, dict) else getattr(cur, part, None)
    return cur


def _set(obj: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _xml_escape(value: Any) -> Any:
    """docxtpl substitutes plain strings straight into the run's XML without
    escaping them itself — an unescaped '&' (e.g. 'Bar Council of
    Maharashtra & Goa') breaks the surrounding XML and docxtpl silently
    drops the bad fragment rather than erroring. Lawyer-entered free text
    (addresses, narratives, names) can easily contain '&', '<' or '>', so
    every string leaf is escaped right before rendering — after all other
    context-building, so markers/formatting above see the original text."""
    if isinstance(value, str):
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if isinstance(value, dict):
        return {k: _xml_escape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_xml_escape(v) for v in value]
    return value


def _blank_nones(value: Any) -> Any:
    """Recursively turn None into "" so a template tag for an unset field
    renders as blank text rather than the literal word 'None'. Required
    leaves get a visible marker instead (see REQUIRED_FIELDS), applied after
    this pass."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return {k: _blank_nones(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_blank_nones(v) for v in value]
    return value


# Required leaf fields per document, as (dotted path into the facts dict,
# human label). A missing value becomes a visible marker in the rendered
# document AND an entry in `gaps` — never silently blank text.
REQUIRED_FIELDS: Dict[str, List[Tuple[str, str]]] = {
    "legal_notice": [
        ("complainant.name", "complainant's name"),
        ("complainant.address", "complainant's address"),
        ("accused.name", "accused's name"),
        ("accused.address", "accused's address"),
        ("advocate.name", "advocate's name"),
        ("advocate.enrolment_no", "advocate's enrolment number"),
        ("transaction.narrative", "transaction narrative"),
        ("notice.amount_demanded", "amount demanded"),
    ],
}


def is_document_applicable(document: DocumentConfig, facts: ChequeBounceFacts) -> bool:
    """The one conditional document in Phase 1: the BSA S.63 certificate is
    only relevant when the notice (or another relied-upon exhibit) exists in
    electronic form."""
    if document.key == "bsa63_certificate":
        return any(m in ("email", "whatsapp") for m in facts.notice.modes)
    return True


def missing_sections(document: DocumentConfig, facts: ChequeBounceFacts) -> List[str]:
    """Section-level readiness: a `requires`d section that's entirely
    untouched (still at its all-None/empty default) blocks generation
    outright — this is coarser than `REQUIRED_FIELDS` and applies to every
    document, including the ones without a field-level map yet."""
    facts_dict = facts.model_dump(mode="json")
    missing = []
    for section in document.requires:
        value = facts_dict.get(section)
        if value in (None, {}, [], ""):
            missing.append(section)
            continue
        if isinstance(value, dict) and not any(v not in (None, "", [], {}) for v in value.values()):
            missing.append(section)
    return missing


def _facts_hash(facts: ChequeBounceFacts) -> str:
    canonical = json.dumps(facts.model_dump(mode="json"), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_context(
    facts: ChequeBounceFacts,
    deadlines: List[DeadlineResult],
    document_key: str,
    today: date,
) -> Tuple[Dict[str, Any], List[str]]:
    """Builds the Jinja context for docxtpl and the list of human-readable
    gap descriptions. Missing required leaves are substituted with a visible
    marker directly in the context so they show up in the rendered text."""
    ctx: Dict[str, Any] = _blank_nones(facts.model_dump(mode="json"))
    gaps: List[str] = []

    cheque = facts.relied_cheque()
    presentment = facts.presentment_for(cheque.number if cheque else None)
    dishonour = facts.dishonour_for(cheque.number if cheque else None)
    ctx["relied_cheque"] = _blank_nones(cheque.model_dump(mode="json")) if cheque else {}
    ctx["relied_presentment"] = _blank_nones(presentment.model_dump(mode="json")) if presentment else {}
    ctx["relied_dishonour"] = _blank_nones(dishonour.model_dump(mode="json")) if dishonour else {}
    ctx["directors_in_charge"] = [
        _blank_nones(d.model_dump(mode="json")) for d in facts.accused.directors if d.in_charge_of_business
    ]

    for path, label in REQUIRED_FIELDS.get(document_key, []):
        if _get(ctx, path) in (None, "", []):
            gaps.append(label)
            _set(ctx, path, MISSING_MARKER.format(label=label))

    ctx["deadlines"] = {d.key: d.__dict__ for d in deadlines}
    ctx["today_long"] = format_date_long(today)
    ctx["is_corporate_accused"] = facts.accused.kind in ("company", "partnership", "llp", "trust")

    if cheque and cheque.amount:
        ctx["cheque_amount_words"] = amount_in_words(cheque.amount)
    if facts.notice.amount_demanded:
        ctx["amount_demanded_words"] = amount_in_words(facts.notice.amount_demanded)
    for date_path, out_key in [
        ("notice.dispatch_date", "notice_dispatch_date_long"),
        ("notice.delivered_on", "notice_delivered_on_long"),
    ]:
        raw = _get(ctx, date_path)
        if raw:
            ctx[out_key] = format_date_long(date.fromisoformat(raw) if isinstance(raw, str) else raw)
    if cheque and cheque.cheque_date:
        d = cheque.cheque_date if isinstance(cheque.cheque_date, date) else date.fromisoformat(str(cheque.cheque_date))
        ctx["cheque_date_long"] = format_date_long(d)
    if dishonour and dishonour.return_memo_date:
        d = (
            dishonour.return_memo_date
            if isinstance(dishonour.return_memo_date, date)
            else date.fromisoformat(str(dishonour.return_memo_date))
        )
        ctx["relied_dishonour"]["return_memo_date_long"] = format_date_long(d)

    return ctx, gaps


def render_document(
    track: TrackConfig,
    document_key: str,
    facts: ChequeBounceFacts,
    today: date,
    *,
    finalised: bool = False,
    template_version: str = "1.0.0",
) -> RenderResult:
    try:
        from docxtpl import DocxTemplate  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised once deps are installed
        raise TemplateRenderError(
            "docxtpl is not installed. Run `pip install -r requirements.txt` "
            "(adds docxtpl + python-docx) before generating documents."
        ) from exc

    document = track.document(document_key)
    if document is None:
        raise TemplateRenderError(f"Unknown document '{document_key}' for track '{track.key}'.")
    if not is_document_applicable(document, facts):
        raise DocumentNotApplicableError(
            f"'{document.title}' does not apply on the current facts — {document.conditional_note or ''}".strip()
        )
    missing = missing_sections(document, facts)
    if missing:
        raise TemplateRenderError(
            f"Cannot generate '{document.title}' yet — these sections are still empty: {', '.join(missing)}."
        )

    deadlines = compute_deadlines(to_deadline_facts(facts), today)
    ctx, gaps = build_context(facts, deadlines, document_key, today)
    ctx["draft_banner"] = not finalised
    facts_hash = _facts_hash(facts)
    ctx["template_version"] = template_version
    ctx["facts_hash_short"] = facts_hash[:12]

    template_path = TEMPLATES_DIR / document.template
    if not template_path.exists():
        raise TemplateRenderError(
            f"Template file missing: {template_path}. Run "
            "scripts/build_drafting_templates.py to generate the Phase-1 templates."
        )

    tpl = DocxTemplate(str(template_path))
    tpl.render(_xml_escape(ctx))
    buf = BytesIO()
    tpl.save(buf)
    return RenderResult(
        content=buf.getvalue(),
        gaps=gaps,
        facts_hash=facts_hash,
        template_version=template_version,
    )
