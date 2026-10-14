"""
Drafting module API (LLD S.9): tracks, matters, deadlines, document
generation. Phase 1 scope — only `cheque_bounce` is enabled
(app.drafting.registry.ENABLED_TRACKS).

Mirrors app/api/routes/groups.py throughout: the Supabase service-role
client bypasses RLS, so ownership is enforced here via `_require_matter`
(same shape as groups.py's `_require_group`), scoped to
`current_user["sub"]`.

Only one track exists yet, so this module imports cheque_bounce's deadline
engine, validation rules and adapter directly rather than dispatching on
`track.facts_model` for everything. The fact MODEL itself is already loaded
generically (see `_load_facts_model`) so a second track can plug in its own
model without touching this file's structure — wiring up a second track's
deadline/validation modules the same way is Phase-2 work, not a redesign.
"""
import importlib
import json
import logging
from datetime import date
from functools import lru_cache
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ValidationError

from app.core.security import get_current_user
from app.drafting import registry
from app.drafting.deadlines.adapters import to_deadline_facts
from app.drafting.deadlines.engine import compute as compute_deadlines
from app.drafting.render.docx_renderer import (
    DocumentNotApplicableError,
    TemplateRenderError,
    is_document_applicable,
    missing_sections,
    render_document,
)
from app.drafting.validation.rules import blocking_issues_for, validate as validate_facts
from app.schemas.schemas import (
    DeadlineOut,
    DocumentConfigOut,
    DocumentReadinessOut,
    FactsPatch,
    Matter,
    MatterCreate,
    MatterDetail,
    MatterDocumentOut,
    ResearchSlotOut,
    StageOut,
    TrackDetail,
    TrackSummary,
    ValidationIssueOut,
)
from app.services.supabase import supabase_service

logger = logging.getLogger(__name__)
router = APIRouter()

MEDIA_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@lru_cache(maxsize=None)
def _load_facts_model(dotted_path: str):
    module_path, _, class_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _parse_facts(track: registry.TrackConfig, raw_facts: dict) -> BaseModel:
    model = _load_facts_model(track.facts_model)
    try:
        return model.model_validate(raw_facts or {})
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Stored facts failed validation: {e}")


def _require_matter(user_id: str, matter_id: str) -> dict:
    matter = supabase_service.get_matter(user_id, matter_id)
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter


def _track_detail(track: registry.TrackConfig) -> TrackDetail:
    return TrackDetail(
        key=track.key,
        title=track.title,
        stages=[StageOut(key=s.key, label=s.label, sections=s.sections) for s in track.stages],
        deadlines=track.deadlines,
        documents=[
            DocumentConfigOut(
                key=d.key, title=d.title, requires=d.requires,
                feature_flag=d.feature_flag, conditional_note=d.conditional_note,
            )
            for d in track.documents
        ],
        research_slots=[ResearchSlotOut(key=r.key, label=r.label) for r in track.research_slots],
    )


# ==================== Tracks ====================

@router.get("/drafting/tracks", response_model=List[TrackSummary])
def list_tracks() -> List[TrackSummary]:
    return [TrackSummary(key=t.key, title=t.title) for t in registry.list_enabled_tracks()]


@router.get("/drafting/tracks/{track_key}", response_model=TrackDetail)
def get_track_detail(track_key: str) -> TrackDetail:
    try:
        track = registry.get_enabled_track(track_key)
    except (registry.TrackNotFoundError, registry.TrackNotEnabledError):
        raise HTTPException(status_code=404, detail="Track not found")
    return _track_detail(track)


# ==================== Matters ====================

@router.post("/drafting/matters", response_model=Matter, status_code=201)
def create_matter(body: MatterCreate, current_user: dict = Depends(get_current_user)) -> Matter:
    if not registry.is_enabled(body.track_key):
        raise HTTPException(status_code=400, detail=f"Track '{body.track_key}' is not enabled")
    row = supabase_service.create_matter(current_user["sub"], body.track_key, body.title)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create matter")
    return Matter(**row)


@router.get("/drafting/matters", response_model=List[Matter])
def list_matters(current_user: dict = Depends(get_current_user)) -> List[Matter]:
    return [Matter(**m) for m in supabase_service.list_matters(current_user["sub"])]


@router.get("/drafting/matters/{matter_id}", response_model=MatterDetail)
def get_matter(matter_id: str, current_user: dict = Depends(get_current_user)) -> MatterDetail:
    row = _require_matter(current_user["sub"], matter_id)
    return MatterDetail(**row)


@router.patch("/drafting/matters/{matter_id}/facts", response_model=MatterDetail)
def patch_facts(
    matter_id: str, body: FactsPatch, current_user: dict = Depends(get_current_user)
) -> MatterDetail:
    row = _require_matter(current_user["sub"], matter_id)
    track = registry.get_enabled_track(row["track_key"])

    merged = dict(row.get("facts") or {})
    existing = merged.get(body.section)
    if isinstance(existing, dict) and isinstance(body.data, dict):
        merged[body.section] = {**existing, **body.data}
    else:
        # List-typed sections (cheques, presentments, dishonours) replace
        # wholesale — there's no meaningful "merge" for a list of records.
        merged[body.section] = body.data

    # Validate the WHOLE merged facts object against the track's model
    # before saving — a patch that makes the facts inconsistent (e.g. a
    # dishonour date before the cheque date) is rejected, not persisted.
    _parse_facts(track, merged)

    updated = supabase_service.update_matter_facts(current_user["sub"], matter_id, merged)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update matter facts")
    return MatterDetail(**updated)


@router.delete("/drafting/matters/{matter_id}", status_code=204)
def delete_matter(matter_id: str, current_user: dict = Depends(get_current_user)) -> Response:
    _require_matter(current_user["sub"], matter_id)
    supabase_service.delete_matter(current_user["sub"], matter_id)
    return Response(status_code=204)


# ==================== Deadlines & readiness ====================

@router.get("/drafting/matters/{matter_id}/deadlines", response_model=List[DeadlineOut])
def get_deadlines(matter_id: str, current_user: dict = Depends(get_current_user)) -> List[DeadlineOut]:
    row = _require_matter(current_user["sub"], matter_id)
    track = registry.get_enabled_track(row["track_key"])
    facts = _parse_facts(track, row.get("facts") or {})
    deadlines = compute_deadlines(to_deadline_facts(facts), today=date.today())
    return [DeadlineOut(**d.__dict__) for d in deadlines]


@router.get("/drafting/matters/{matter_id}/readiness", response_model=List[DocumentReadinessOut])
def get_readiness(matter_id: str, current_user: dict = Depends(get_current_user)) -> List[DocumentReadinessOut]:
    """Per-document generation readiness: missing sections + blocking
    validation issues, so the wizard can grey out a document before the
    lawyer even tries to generate it."""
    row = _require_matter(current_user["sub"], matter_id)
    track = registry.get_enabled_track(row["track_key"])
    facts = _parse_facts(track, row.get("facts") or {})
    deadlines = compute_deadlines(to_deadline_facts(facts), today=date.today())
    issues = validate_facts(facts, deadlines, today=date.today())

    out = []
    for doc in track.documents:
        blocking = blocking_issues_for(issues, doc.key)
        out.append(
            DocumentReadinessOut(
                key=doc.key,
                title=doc.title,
                applicable=is_document_applicable(doc, facts),
                missing_sections=missing_sections(doc, facts),
                blocking_issues=[
                    ValidationIssueOut(
                        rule=i.rule, severity=i.severity, message=i.message,
                        field_path=i.field_path, applies_to_documents=i.applies_to_documents,
                    )
                    for i in blocking
                ],
            )
        )
    return out


# ==================== Document generation ====================

@router.post("/drafting/matters/{matter_id}/documents/{template_key}")
def generate_document(
    matter_id: str, template_key: str, current_user: dict = Depends(get_current_user)
) -> Response:
    row = _require_matter(current_user["sub"], matter_id)
    track = registry.get_enabled_track(row["track_key"])
    facts = _parse_facts(track, row.get("facts") or {})

    today = date.today()
    deadlines = compute_deadlines(to_deadline_facts(facts), today=today)
    issues = validate_facts(facts, deadlines, today=today)
    blocking = blocking_issues_for(issues, template_key)
    if blocking:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This document is blocked by unresolved legal-correctness issues.",
                "issues": [
                    {"rule": i.rule, "message": i.message, "field_path": i.field_path}
                    for i in blocking
                ],
            },
        )

    try:
        result = render_document(track, template_key, facts, today=today)
    except DocumentNotApplicableError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TemplateRenderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    supabase_service.record_matter_document(
        current_user["sub"], matter_id, template_key, result.template_version,
        result.facts_hash, result.gaps,
    )

    return Response(
        content=result.content,
        media_type=MEDIA_TYPE_DOCX,
        headers={
            "Content-Disposition": f'attachment; filename="{template_key}.docx"',
            "X-Gaps": json.dumps(result.gaps),
        },
    )


@router.get("/drafting/matters/{matter_id}/documents", response_model=List[MatterDocumentOut])
def list_matter_documents(
    matter_id: str, current_user: dict = Depends(get_current_user)
) -> List[MatterDocumentOut]:
    _require_matter(current_user["sub"], matter_id)
    return [MatterDocumentOut(**d) for d in supabase_service.list_matter_documents(matter_id)]


@router.post("/drafting/matters/{matter_id}/documents/{document_id}/finalise", response_model=MatterDocumentOut)
def finalise_document(
    matter_id: str, document_id: str, current_user: dict = Depends(get_current_user)
) -> MatterDocumentOut:
    _require_matter(current_user["sub"], matter_id)
    row = supabase_service.finalise_matter_document(current_user["sub"], matter_id, document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return MatterDocumentOut(**row)
