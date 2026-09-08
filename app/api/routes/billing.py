"""
Billing routes: plan/usage readout, subscription creation, and the gateway webhook.

The webhook — not the browser return — is the source of truth for tier changes,
so a user who pays and closes the tab is still upgraded.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.quota import effective_limit, start_of_month_utc
from app.core.security import get_current_user
from app.core.tiers import purchasable_tiers, tier_for_plan
from app.services.billing import get_billing_provider
from app.services.supabase import supabase_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/billing/me")
def billing_me(current_user: dict = Depends(get_current_user)) -> dict:
    """Current plan + this-month usage — powers the NavRail badge and pricing page."""
    uid = current_user.get("sub")
    profile = supabase_service.get_profile(uid)
    limit = effective_limit(profile)
    used = supabase_service.count_searches_since(uid, start_of_month_utc())
    return {
        "tier": profile.get("tier", "free"),
        "searches_used": used,
        "searches_limit": limit,          # None = unlimited
        "period_end": profile.get("current_period_end"),
        "status": profile.get("subscription_status"),
    }


@router.get("/billing/tiers")
def billing_tiers() -> dict:
    """Purchasable plans for the pricing page — data-driven from the tier registry."""
    return {
        "tiers": [
            {"key": t.key, "label": t.label, "monthly_limit": t.monthly_limit}
            for t in purchasable_tiers()
        ]
    }


@router.post("/billing/subscribe")
def billing_subscribe(current_user: dict = Depends(get_current_user)) -> dict:
    """Start a Pro subscription; returns the fields the frontend checkout needs."""
    uid = current_user.get("sub")
    email = current_user.get("email")
    provider = get_billing_provider()
    try:
        result = provider.create_subscription(uid, email)
    except Exception as e:
        logger.error(f"❌ create_subscription failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Could not start subscription")

    # Record the pending subscription id now (tier stays until the webhook confirms
    # payment) so we can reconcile even if the webhook's notes are ever missing.
    supabase_service.update_subscription(
        user_id=uid,
        provider=provider.name,
        provider_subscription_id=result.get("subscription_id"),
        subscription_status="created",
    )
    return result


@router.post("/billing/webhook")
async def billing_webhook(request: Request) -> dict:
    """Gateway callback. Verifies the signature, then applies the tier change."""
    provider = get_billing_provider()
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not provider.verify_webhook(raw, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed webhook body")

    event = provider.parse_event(payload)
    if event.type == "ignored" or not event.user_id:
        return {"ok": True, "ignored": True}

    if event.type in ("activated", "charged"):
        # Resolve which paid tier this plan grants (defaults to "pro" so a single
        # plan keeps working even if plan_id isn't in the payload).
        granted = tier_for_plan(event.plan_id)
        tier = granted.key if granted else "pro"
        supabase_service.update_subscription(
            user_id=event.user_id,
            tier=tier,
            provider=provider.name,
            provider_subscription_id=event.subscription_id,
            subscription_status=event.status,
            current_period_end=event.current_period_end,
        )
        logger.info(f"✅ {tier} granted/renewed for {event.user_id} ({event.type})")
    elif event.type in ("halted", "cancelled"):
        supabase_service.update_subscription(
            user_id=event.user_id,
            tier="free",
            provider=provider.name,
            provider_subscription_id=event.subscription_id,
            subscription_status=event.status,
        )
        logger.info(f"⬇️ Downgraded {event.user_id} to free ({event.type})")

    return {"ok": True}
