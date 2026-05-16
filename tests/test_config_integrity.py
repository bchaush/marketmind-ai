from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_config(name: str) -> dict:
    path = REPO_ROOT / "config" / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_scoring_config_integrity():
    # 1. Both config files load as valid JSON without errors
    weights = _load_config("scoring_weights.json")
    thresholds = _load_config("scoring_thresholds.json")
    assert isinstance(weights, dict)
    assert isinstance(thresholds, dict)

    # 2. scoring_weights.json spec_version
    assert weights["spec_version"] == "phase2_scoring_spec_v0.1"

    # 3. scoring_thresholds.json spec_version
    assert thresholds["spec_version"] == "phase2_scoring_spec_v0.1"

    # 4. Every weight block sums to 1.0 (tolerance 0.001)
    tol = 0.001
    blocks = [
        "demand_score",
        "competition_pressure_score",
        "market_gap_score",
        "risk_score",
        "opportunity_score",
        "confidence_score",
    ]
    for block in blocks:
        w = weights[block]
        total = sum(w.values())
        assert abs(total - 1.0) <= tol, f"{block} weights sum to {total}, expected 1.0 ± {tol}"

    # 5. All required keys exist in scoring_thresholds.json
    required = [
        "normalization",
        "null_handling",
        "confidence_floors",
        "geography_fidelity",
        "band_thresholds",
        "edge_cases",
        "anchor_metrics",
    ]
    for key in required:
        assert key in thresholds

    # 6. anchor_metrics["coffee_shop"]
    assert thresholds["anchor_metrics"]["coffee_shop"] == ["pop_total", "age_22_34_count"]
