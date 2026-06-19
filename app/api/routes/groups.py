"""
Groups + group-scoped annotations for the PDF reader (Phase 2).

A group is a user's collection of cases; annotations are stored ONE ROW PER
GESTURE (its `rects` array carries every PDF-native rectangle it covers).

The Supabase service-role client bypasses RLS, so ownership is enforced here:
every route is scoped to `current_user["sub"]`, and child routes (items,
annotations) first verify the parent group is owned by the caller.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.security import get_current_user
from app.schemas.schemas import (
    AddCaseRequest,
    Annotation,
    AnnotationCreate,
    AnnotationUpdate,
    Group,
    GroupCreate,
    GroupDetail,
    GroupItem,
    GroupUpdate,
)
from app.services.supabase import supabase_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_group(user_id: str, group_id: str) -> dict:
    """Ownership gate: 404 unless the group exists AND belongs to the caller."""
    group = supabase_service.get_group(user_id, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


# ==================== Groups ====================

@router.post("/groups", response_model=Group, status_code=201)
def create_group(body: GroupCreate, current_user: dict = Depends(get_current_user)) -> Group:
    row = supabase_service.create_group(current_user["sub"], body.name)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create group")
    return Group(**row)


@router.get("/groups", response_model=List[Group])
def list_groups(
    case_id: Optional[str] = Query(None, description="Flag groups already containing this case"),
    current_user: dict = Depends(get_current_user),
) -> List[Group]:
    return [Group(**g) for g in supabase_service.list_groups(current_user["sub"], case_id)]


@router.get("/groups/{group_id}", response_model=GroupDetail)
def get_group(group_id: str, current_user: dict = Depends(get_current_user)) -> GroupDetail:
    group = _require_group(current_user["sub"], group_id)
    items = supabase_service.list_group_items(group_id)
    group["item_count"] = len(items)
    return GroupDetail(**group, items=[GroupItem(**it) for it in items])


@router.patch("/groups/{group_id}", response_model=Group)
def update_group(group_id: str, body: GroupUpdate, current_user: dict = Depends(get_current_user)) -> Group:
    _require_group(current_user["sub"], group_id)
    row = supabase_service.update_group(current_user["sub"], group_id, body.name)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to update group")
    return Group(**row)


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: str, current_user: dict = Depends(get_current_user)) -> Response:
    _require_group(current_user["sub"], group_id)
    supabase_service.delete_group(current_user["sub"], group_id)
    return Response(status_code=204)


# ==================== Group items (cases) ====================

@router.post("/groups/{group_id}/items", response_model=GroupItem, status_code=201)
def add_case(group_id: str, body: AddCaseRequest, current_user: dict = Depends(get_current_user)) -> GroupItem:
    _require_group(current_user["sub"], group_id)
    row = supabase_service.add_group_item(group_id, body.case_id)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to add case to group")
    return GroupItem(**row)


@router.delete("/groups/{group_id}/items/{case_id}", status_code=204)
def remove_case(group_id: str, case_id: str, current_user: dict = Depends(get_current_user)) -> Response:
    _require_group(current_user["sub"], group_id)
    supabase_service.remove_group_item(group_id, case_id)
    return Response(status_code=204)


# ==================== Annotations ====================

@router.get("/groups/{group_id}/annotations", response_model=List[Annotation])
def list_annotations(
    group_id: str,
    case_id: str = Query(..., description="Case whose annotations to load"),
    current_user: dict = Depends(get_current_user),
) -> List[Annotation]:
    _require_group(current_user["sub"], group_id)
    return [Annotation(**r) for r in supabase_service.list_annotations(group_id, case_id)]


@router.post("/groups/{group_id}/annotations", response_model=Annotation, status_code=201)
def create_annotation(
    group_id: str, body: AnnotationCreate, current_user: dict = Depends(get_current_user)
) -> Annotation:
    _require_group(current_user["sub"], group_id)
    payload = {
        "case_id": body.case_id,
        "type": body.type,
        "rects": [r.model_dump() for r in body.rects],
        "color": body.color,
        "comment": body.comment,
    }
    row = supabase_service.create_annotation(current_user["sub"], group_id, payload)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create annotation")
    return Annotation(**row)


@router.patch("/groups/{group_id}/annotations/{annotation_id}", response_model=Annotation)
def update_annotation(
    group_id: str,
    annotation_id: str,
    body: AnnotationUpdate,
    current_user: dict = Depends(get_current_user),
) -> Annotation:
    _require_group(current_user["sub"], group_id)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    row = supabase_service.update_annotation(current_user["sub"], group_id, annotation_id, fields)
    if not row:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return Annotation(**row)


@router.delete("/groups/{group_id}/annotations/{annotation_id}", status_code=204)
def delete_annotation(
    group_id: str, annotation_id: str, current_user: dict = Depends(get_current_user)
) -> Response:
    _require_group(current_user["sub"], group_id)
    supabase_service.delete_annotation(current_user["sub"], group_id, annotation_id)
    return Response(status_code=204)
