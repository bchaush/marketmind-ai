from __future__ import annotations

from unittest.mock import patch

import pipeline.cache as cache_mod
import pytest

from pipeline import live_adapter
from pipeline.live_adapter import fetch_live_bundle


def test_cache_hit_skips_geofence_fetch_and_assembler(monkeypatch):
    fake_bundle = {
        "query": {"lat": 42.35, "lng": -71.105, "business_type": "coffee_shop", "radius_miles": 1.0},
        "competitor_data": {"source": "google_places"},
        "demographic_data": {"source": "census_acs5"},
        "location_signals": {},
        "data_quality": {},
        "phase_1_validation": {},
    }
    monkeypatch.setattr(live_adapter, "get", lambda key: fake_bundle)

    with patch.object(live_adapter, "distance_miles") as dist_mock:
        with patch.object(live_adapter, "fetch_competitors_with_retry") as g_mock:
            with patch.object(live_adapter, "fetch_census_with_retry") as c_mock:
                with patch.object(live_adapter, "assemble") as asm_mock:
                    with patch.object(live_adapter, "set") as set_mock:
                        out = fetch_live_bundle(42.35, -71.105, "coffee_shop")
    assert out is fake_bundle
    dist_mock.assert_not_called()
    g_mock.assert_not_called()
    c_mock.assert_not_called()
    asm_mock.assert_not_called()
    set_mock.assert_not_called()


def test_cache_miss_calls_both_fetchers_and_assembler(tmp_path, monkeypatch):
    monkeypatch.setattr(live_adapter, "get", lambda key: None)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "live_bundles")
    cache_mod.init_cache_dir()

    comp = {"source": "google_places", "summary": {"total_count": 1, "avg_rating": 4.0, "top_3_review_share_pct": 10.0}}
    cens = {
        "source": "census_acs5",
        "pop_total": 100,
        "age_22_34_count": None,
        "median_household_income": None,
        "college_student_population_pct": None,
        "rent_to_income_ratio": None,
        "geography_level": "block_group",
        "confidence_score": 90,
        "fallback_used": [],
    }

    with patch.object(live_adapter, "distance_miles", return_value=0.1):
        with patch.object(live_adapter, "fetch_competitors_with_retry", return_value=comp) as g_mock:
            with patch.object(live_adapter, "fetch_census_with_retry", return_value=cens) as c_mock:
                with patch.object(live_adapter, "assemble", wraps=live_adapter.assemble) as asm_wrapped:
                    out = fetch_live_bundle(42.35, -71.105, "coffee_shop", radius_miles=1.0)

    g_mock.assert_called_once()
    c_mock.assert_called_once()
    assert asm_wrapped.call_count == 1
    assert out["competitor_data"] == comp
    assert out["data_quality"]["google_live"] is True
    assert out["data_quality"]["census_live"] is True
    assert out["_cache_meta"]["cache_hit"] is False
    assert out["_cache_meta"]["key"] == cache_mod.make_cache_key(
        42.35, -71.105, "coffee_shop", 1.0
    )


def test_out_of_geofence_raises_value_error(monkeypatch):
    monkeypatch.setattr(live_adapter, "get", lambda key: None)

    with patch.object(live_adapter, "distance_miles", return_value=4.0):
        with pytest.raises(ValueError, match="outside the supported Boston area"):
            fetch_live_bundle(42.35, -71.105, "coffee_shop")


def test_build_query_validation_propagates():
    with pytest.raises(ValueError, match="lat must be between"):
        fetch_live_bundle(91.0, -71.105, "coffee_shop")


def test_both_sources_called_independently_on_cache_miss(monkeypatch):
    monkeypatch.setattr(live_adapter, "get", lambda key: None)

    comp = {"source": "google_places", "summary": {"total_count": None, "avg_rating": None, "top_3_review_share_pct": None}}
    cens = {
        "source": "census_acs5",
        "pop_total": None,
        "age_22_34_count": None,
        "median_household_income": None,
        "college_student_population_pct": None,
        "rent_to_income_ratio": None,
        "geography_level": None,
        "confidence_score": None,
        "fallback_used": ["live_adapter_census_failure"],
    }

    with patch.object(live_adapter, "distance_miles", return_value=0.5):
        with patch.object(live_adapter, "fetch_competitors_with_retry", return_value=comp) as g_mock:
            with patch.object(live_adapter, "fetch_census_with_retry", return_value=cens) as c_mock:
                fetch_live_bundle(42.35, -71.105, "coffee_shop")

    assert g_mock.call_count == 1
    assert c_mock.call_count == 1
    assert g_mock.call_args == c_mock.call_args
