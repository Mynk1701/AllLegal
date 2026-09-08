"""
Razorpay implementation of BillingProvider.

Uses Razorpay Subscriptions (monthly Pro plan created in the dashboard, id in
settings.RAZORPAY_PLAN_ID). The user's Supabase id travels in the subscription
`notes`, so the webhook can resolve the profile with no extra lookup.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from .base import BillingProvider, NormalizedEvent

logger = logging.getLogger(__name__)

# Razorpay subscription events -> our vocabulary (see
# https://razorpay.com/docs/webhooks/subscriptions/). Grant on activated/charged/
# resumed; revoke on halted/cancelled/paused/completed (`completed` = all cycles
# billed, so the paid term is over). `pending` (a failed charge awaiting retry) is
# deliberately NOT mapped: we keep access during the retry window and let
# current_period_end lapse naturally if it's never recovered.
_EVENT_MAP = {
    "subscription.activated": "activated",
    "subscription.charged": "charged",
    "subscription.resumed": "activated",
    "subscription.halted": "halted",
    "subscription.paused": "cancelled",
    "subscription.cancelled": "cancelled",
    "subscription.completed": "cancelled",
}

# How many monthly cycles a subscription runs before Razorpay stops billing.
# 12 = auto-renews for a year; the `subscription.charged` webhook extends
# current_period_end each month, so access tracks payments regardless.
_TOTAL_CYCLES = 12


class RazorpayProvider(BillingProvider):
    name = "razorpay"

    def __init__(self):
        # Imported lazily so the app boots even if the SDK/keys aren't present
        # (e.g. a deploy that doesn't use billing yet). Only fails if actually used.
        import razorpay

        self._client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    def create_subscription(self, user_id: str, email: Optional[str]) -> dict:
        sub = self._client.subscription.create({
            "plan_id": settings.RAZORPAY_PLAN_ID,
            "total_count": _TOTAL_CYCLES,
            "customer_notify": 1,
            # user_id rides here so billing_webhook can map the event back to a profile.
            "notes": {"user_id": user_id, "email": email or ""},
        })
        return {"subscription_id": sub["id"], "key_id": settings.RAZORPAY_KEY_ID}

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        try:
            self._client.utility.verify_webhook_signature(
                raw_body.decode("utf-8"), signature, settings.RAZORPAY_WEBHOOK_SECRET
            )
            return True
        except Exception as e:
            logger.warning(f"Razorpay webhook signature verification failed: {e}")
            return False

    def parse_event(self, payload: dict) -> NormalizedEvent:
        event = payload.get("event", "")
        entity = (
            payload.get("payload", {})
            .get("subscription", {})
            .get("entity", {})
        )
        notes = entity.get("notes") or {}
        # current_end is the epoch when the current paid cycle ends; charge_at is
        # the next attempt. Prefer current_end for the access window.
        epoch = entity.get("current_end") or entity.get("charge_at")
        period_end = (
            datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat() if epoch else None
        )
        return NormalizedEvent(
            type=_EVENT_MAP.get(event, "ignored"),
            user_id=notes.get("user_id"),
            subscription_id=entity.get("id"),
            status=entity.get("status"),
            current_period_end=period_end,
            plan_id=entity.get("plan_id"),
        )
