"""
Per-user search quota enforcement.

A single FastAPI dependency (`enforce_search_quota`) layered after
`get_current_user` on the one billable route (GET /api/search). The per-tier caps
live in app/core/tiers.py, so this logic is tier-count-agnostic:
  - unlimited tiers (monthly_limit=None)  -> always allowed
  - paid tier whose subscription lapsed   -> metered at the Free cap
  - metered tiers                         -> N searches per calendar month

Usage is counted from the existing `search_logs` ledger (no separate counter).
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException

from app.core.security import get_current_user
from app.core.tiers import get_tier
from app.services.supabase import supabase_service

logger = logging.getLogger(__name__)


def start_of_month_utc() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _subscription_active(profile: dict) -> bool:
    """True iff the profile's paid term hasn't lapsed (current_period_end future)."""
    cpe = profile.get("current_period_end")
    if not cpe:
        return False
    try:
        return datetime.fromisoformat(cpe) >= datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def effective_limit(profile: dict) -> Optional[int]:
    """The user's monthly search cap right now (None = unlimited).

    A paid tier only counts as unlimited while its subscription is active; once
    lapsed it's metered at the Free cap until a renewal webhook restores it.
    """
    spec = get_tier(profile.get("tier"))
    if spec.requires_subscription and not _subscription_active(profile):
        return get_tier("free").monthly_limit
    return spec.monthly_limit


def is_unlimited(profile: dict) -> bool:
    return effective_limit(profile) is None


async def enforce_search_quota(current_user: dict = Depends(get_current_user)) -> dict:
    """Raise 429 if a metered user is over their monthly allowance. Returns the
    same JWT payload as get_current_user so downstream code is unchanged."""
    uid = current_user.get("sub")
    profile = supabase_service.get_profile(uid)
    limit = effective_limit(profile)
    if limit is None:
        return current_user

    used = supabase_service.count_searches_since(uid, start_of_month_utc())
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "used": used,
                "limit": limit,
                "tier": profile.get("tier", "free"),
            },
        )
    return current_user
