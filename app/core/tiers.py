"""
Single source of truth for billing tiers.

To add a tier in future, add ONE entry here (plus the matching value in the
`profiles.tier` CHECK constraint in Supabase, and a Razorpay plan if it's paid).
Quota enforcement (app/core/quota.py), the billing routes (app/api/routes/
billing.py), and the /billing/tiers endpoint all read from this registry — no
other backend code needs to change.

Fields:
  - monthly_limit: searches allowed per calendar month; None = unlimited.
  - requires_subscription: True = a paid tier whose access is gated by an active
    subscription (current_period_end in the future). Granted/revoked by webhooks;
    when lapsed, the user is metered at the FREE tier's limit.
  - plan_id: the gateway plan to subscribe to for a paid tier (None otherwise).
  - purchasable: shown on the pricing page as something a user can buy.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from app.core.config import settings


@dataclass(frozen=True)
class TierSpec:
    key: str
    label: str
    monthly_limit: Optional[int]      # None = unlimited
    requires_subscription: bool = False
    plan_id: Optional[str] = None
    purchasable: bool = False


@lru_cache(maxsize=1)
def _registry() -> dict[str, TierSpec]:
    return {
        "free": TierSpec(
            key="free", label="Free",
            monthly_limit=settings.FREE_TIER_SEARCH_LIMIT,
        ),
        "pro": TierSpec(
            key="pro", label="Pro",
            monthly_limit=None,               # unlimited
            requires_subscription=True,
            plan_id=settings.RAZORPAY_PLAN_ID,
            purchasable=True,
        ),
        "internal": TierSpec(
            key="internal", label="Internal",
            monthly_limit=None,               # unlimited, comped
        ),
    }


DEFAULT_TIER = "free"


def get_tier(key: Optional[str]) -> TierSpec:
    """Resolve a tier by key, falling back to Free for unknown/None."""
    return _registry().get(key or DEFAULT_TIER, _registry()[DEFAULT_TIER])


def purchasable_tiers() -> list[TierSpec]:
    return [t for t in _registry().values() if t.purchasable]


def tier_for_plan(plan_id: Optional[str]) -> Optional[TierSpec]:
    """Map a gateway plan id back to its tier (used by the webhook so a new paid
    tier is granted correctly without touching billing.py). None if unmatched."""
    if not plan_id:
        return None
    for t in _registry().values():
        if t.plan_id and t.plan_id == plan_id:
            return t
    return None
