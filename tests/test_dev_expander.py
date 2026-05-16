"""Phase 7 C1 Developer View payload."""

from __future__ import annotations

import json
from typing import Any

from ui.dev_payload import build_dev_payload

_REQUIRED_KEYS = frozenset(
    [
        "scores",
        "final_status",
        "confidence_score",
        "cache_key",
        "data_quality",
        "fallback_level",
        "scoring_weights",
    ]
)


def test_dev_payload_contains_required_keys() -> None:
    ui_payload: dict[str, Any] = {
        "scores": {"confidence_score": 72.5, "demand_score": 50.0},
        "status": {"final_status": "CAUTION"},
    }
    live_bundle = {
        "data_quality": {"google_live": True, "census_live": True},
        "demographic_data": {"fallback_level": "block_group"},
        "query": {"lat": 42.0, "lng": -71.0},
    }
    out = build_dev_payload(ui_payload, live_bundle, "test-cache-key")
    assert _REQUIRED_KEYS <= frozenset(out.keys())


def test_dev_payload_excludes_secrets() -> None:
    ui_payload: dict[str, Any] = {
        "scores": {"confidence_score": 1.0},
        "status": {"final_status": "GO"},
    }
    live_bundle = {"data_quality": {}, "demographic_data": {}}
    out = build_dev_payload(ui_payload, live_bundle, "k")
    blob = json.dumps(out)
    lower = blob.lower()
    for needle in ("api_key", "secret", "password", "token"):
        assert needle not in lower
    assert "API_KEY" not in blob


def test_dev_payload_coordinates_rounded() -> None:
    precise = 42.123456789
    rounded_lat = round(precise, 3)
    ui_payload: dict[str, Any] = {"scores": {}, "status": {"final_status": ""}}
    live_bundle = {"query": {"lat": precise, "lng": -71.987654321}}
    out = build_dev_payload(ui_payload, live_bundle, "k")
    assert out["location"]["lat"] == rounded_lat
    assert out["location"]["lng"] == round(-71.987654321, 3)
