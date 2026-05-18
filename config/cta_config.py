"""Dual-persona footer CTA (Phase 7 B2); controlled via CTA_MODE env var."""

from __future__ import annotations

import copy
import os
from typing import Any

_RECRUITER_CONFIG: dict[str, Any] = {
    "headline": "Built by Bora Chaush",
    "subtext": "Full-stack AI system · Real APIs · Deterministic scoring engine",
    "link_label": "View on GitHub",
    "link_url": "https://github.com/bchaush/marketmind-ai",
    "secondary_label": None,
    "secondary_url": None,
}

_STARTUP_CONFIG: dict[str, Any] = {
    "headline": "MarketMind AI",
    "subtext": "Market entry intelligence for Boston-area operators and investors.",
    "link_label": "Request Early Access",
    "link_url": "mailto:[your-email]",
    "secondary_label": None,
    "secondary_url": None,
}


def get_cta_config() -> dict[str, Any]:
    mode = os.getenv("CTA_MODE", "recruiter").strip().lower()
    if mode == "startup":
        return copy.deepcopy(_STARTUP_CONFIG)
    return copy.deepcopy(_RECRUITER_CONFIG)
