from __future__ import annotations

import json
from pathlib import Path

from pipeline import bundle_assembler


def test_assemble_produces_exact_six_top_level_keys():
    query = {"lat": 42.35, "lng": -71.105, "business_type": "coffee_shop"}
    comp_raw = {
        "source": "google_places",
        "summary": {"total_count": 5, "avg_rating": 4.1, "top_3_review_share_pct": 20.0},
    }
    census_raw = {"source": "census_acs5", "pop_total": 5000, "geography_level": "block_group"}
    bundle = bundle_assembler.assemble(query, comp_raw, census_raw)
    expected_keys = {
        "query",
        "competitor_data",
        "demographic_data",
        "location_signals",
        "data_quality",
        "phase_1_validation",
    }
    assert set(bundle.keys()) == expected_keys
    assert bundle["data_quality"]["google_live"] is True
    assert bundle["data_quality"]["census_live"] is True
    assert bundle["phase_1_validation"]["passed"] is True
    assert bundle["phase_1_validation"]["google_data_present"] is True
    assert bundle["phase_1_validation"]["census_data_present"] is True


def test_assemble_handles_degraded_stubs_correctly():
    query = {"lat": 42.35, "lng": -71.105, "business_type": "coffee_shop"}
    comp_stub = {
        "source": "google_places",
        "summary": {"total_count": None, "avg_rating": None, "top_3_review_share_pct": None},
    }
    census_stub = {"source": "census_acs5", "pop_total": None, "geography_level": None}
    bundle = bundle_assembler.assemble(query, comp_stub, census_stub)
    assert bundle["data_quality"]["google_live"] is False
    assert bundle["data_quality"]["census_live"] is False
    assert bundle["phase_1_validation"]["passed"] is True
    assert bundle["phase_1_validation"]["google_data_present"] is False
    assert bundle["phase_1_validation"]["census_data_present"] is False


def test_assemble_is_pure_and_deep_copies_inputs():
    query = {"lat": 42.35, "lng": -71.105, "meta": {"label": "test"}}
    comp_raw = {"summary": {"total_count": 10}}
    census_raw = {"pop_total": 100}
    bundle = bundle_assembler.assemble(query, comp_raw, census_raw)
    query["meta"]["label"] = "mutated"
    comp_raw["summary"]["total_count"] = 999
    assert bundle["query"]["meta"]["label"] == "test"
    assert bundle["competitor_data"]["summary"]["total_count"] == 10


def test_assemble_top_level_keys_match_mock_contract():
    mock = json.loads(Path("mock_data/mock_boston_data.json").read_text(encoding="utf-8"))
    query = {"lat": 42.35, "lng": -71.105, "business_type": "coffee_shop"}
    comp_raw = {
        "source": "google_places",
        "summary": {"total_count": 5, "avg_rating": 4.1, "top_3_review_share_pct": 20.0},
    }
    census_raw = {"source": "census_acs5", "pop_total": 5000}
    bundle = bundle_assembler.assemble(query, comp_raw, census_raw)
    assert set(bundle.keys()) == set(mock.keys())
