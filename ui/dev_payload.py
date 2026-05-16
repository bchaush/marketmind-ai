"""Sanitized Developer View payload (pure; no Streamlit, no secrets)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def _round_coord_3dp(value: Any) -> float | None:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def build_dev_payload(
    ui_payload: Mapping[str, Any],
    live_bundle: Mapping[str, Any],
    cache_key: str,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Assemble technical snapshot for auditors (no API keys, raw responses, or paths)."""
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[1]
    weights_path = root / "config" / "scoring_weights.json"
    with weights_path.open("r", encoding="utf-8") as wf:
        scoring_weights = json.load(wf)

    scores = dict(ui_payload.get("scores") or {})
    status = ui_payload.get("status") if isinstance(ui_payload.get("status"), dict) else {}
    final_status = status.get("final_status")
    confidence_score = scores.get("confidence_score")

    dq_raw = live_bundle.get("data_quality") if isinstance(live_bundle.get("data_quality"), dict) else {}
    data_quality = dict(dq_raw) if dq_raw else {}

    demo = (
        live_bundle.get("demographic_data")
        if isinstance(live_bundle.get("demographic_data"), dict)
        else {}
    )
    raw_fallback = demo.get("fallback_level")
    if raw_fallback is None:
        fallback_level: str = "live"
    elif isinstance(raw_fallback, str):
        fallback_level = raw_fallback
    else:
        fallback_level = str(raw_fallback)

    query = live_bundle.get("query") if isinstance(live_bundle.get("query"), dict) else {}
    location: dict[str, float] = {}
    lat_r = _round_coord_3dp(query.get("lat"))
    if lat_r is not None:
        location["lat"] = lat_r
    lng_r = _round_coord_3dp(query.get("lng"))
    if lng_r is not None:
        location["lng"] = lng_r

    out: dict[str, Any] = {
        "scoring_weights": scoring_weights,
        "scores": scores,
        "final_status": final_status,
        "confidence_score": confidence_score,
        "cache_key": cache_key,
        "data_quality": data_quality,
        "fallback_level": fallback_level,
    }
    if location:
        out["location"] = location
    return out
