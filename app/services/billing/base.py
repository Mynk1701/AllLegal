"""
Gateway-agnostic billing interface.

The quota/tier logic (app/core/quota.py, app/api/routes/billing.py) talks only to
this abstraction, so a second gateway (e.g. Stripe) can be added later by writing
one more BillingProvider subclass — no changes to routes or the quota gate.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedEvent:
    """A gateway webhook mapped onto our own vocabulary.

    `type` is one of:
      - "activated" / "charged"  -> grant/renew Pro
      - "halted" / "cancelled"   -> downgrade to Free
      - "ignored"                -> a webhook we don't act on
    `user_id` is our Supabase auth id, carried through the gateway's subscription
    `notes`/metadata so the webhook can find the right profile without a lookup.
    """
    type: str
    user_id: Optional[str] = None
    subscription_id: Optional[str] = None
    status: Optional[str] = None
    current_period_end: Optional[str] = None  # ISO 8601 UTC
    plan_id: Optional[str] = None  # gateway plan id -> resolves the target tier


class BillingProvider(ABC):
    name: str

    @abstractmethod
    def create_subscription(self, user_id: str, email: Optional[str]) -> dict:
        """Create a recurring subscription for the user. Returns the fields the
        frontend checkout needs, e.g. {"subscription_id": ..., "key_id": ...}."""

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        """True iff `raw_body` is an authentic webhook (HMAC/signature check)."""

    @abstractmethod
    def parse_event(self, payload: dict) -> NormalizedEvent:
        """Map a verified webhook payload to a NormalizedEvent."""
