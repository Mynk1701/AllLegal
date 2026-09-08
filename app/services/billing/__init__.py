"""Billing provider factory. `get_billing_provider()` returns the configured
gateway (Razorpay today); swap via settings.BILLING_PROVIDER."""
from functools import lru_cache

from app.core.config import settings
from .base import BillingProvider, NormalizedEvent


@lru_cache(maxsize=1)
def get_billing_provider() -> BillingProvider:
    provider = (settings.BILLING_PROVIDER or "razorpay").lower()
    if provider == "razorpay":
        from .razorpay_provider import RazorpayProvider
        return RazorpayProvider()
    raise ValueError(f"Unknown BILLING_PROVIDER: {settings.BILLING_PROVIDER!r}")


__all__ = ["BillingProvider", "NormalizedEvent", "get_billing_provider"]
