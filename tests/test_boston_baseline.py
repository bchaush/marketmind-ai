"""Boston Suffolk County ACS baseline seeded fallback (Phase 7 A2)."""

from __future__ import annotations

import json
from pathlib import Path

from data_layer.census_api import CensusData

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "boston_baseline.json"
_BASELINE_META_KEYS = {"_source", "_note"}
_EXPECTED_METRIC_KEYS = {
    "pop_total",
    "median_household_income",
    "median_age",
    "college_student_population_pct",
    "age_22_34_count",
    "rent_to_income_ratio",
}


def test_baseline_values_are_not_none() -> None:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        baseline = json.load(f)
    for key in sorted(_EXPECTED_METRIC_KEYS):
        assert key in baseline, f"missing key {key}"
        assert baseline[key] is not None, f"{key} must not be None"


def test_baseline_json_matches_census_data_fields() -> None:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        baseline = json.load(f)
    model_fields = CensusData.model_fields
    for key in baseline:
        if key in _BASELINE_META_KEYS:
            continue
        assert key in model_fields, f"boston_baseline key {key!r} is not a CensusData field"
