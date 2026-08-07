"""Live-UI scope constants. Only coffee_shop is supported end-to-end today."""

from __future__ import annotations

LIVE_BUSINESS_TYPE = "coffee_shop"
LIVE_BUSINESS_TYPE_LABEL = "Coffee shop"


def get_live_business_type() -> str:
    """Canonical business type passed into the live analysis pipeline."""
    return LIVE_BUSINESS_TYPE
