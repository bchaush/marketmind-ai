"""Tests for bundle _cache_meta (hit vs miss, stripping before scoring)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import pipeline.cache as cache_mod
from pipeline import live_adapter
from pipeline.live_adapter import fetch_live_bundle


@pytest.fixture
def isolated_cache_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    cache_root = tmp_path / "live_bundles"
    monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_root)
    monkeypatch.setattr(cache_mod, "CACHE_TTL_DAYS", 14)
    cache_mod.init_cache_dir()
    yield cache_root


def test_cache_hit_injects_meta(isolated_cache_dir):
    bundle = {
        "query": {
            "lat": 42.3505,
            "lng": -71.1054,
            "business_type": "coffee_shop",
            "radius_miles": 1.0,
        },
        "competitor_data": {"source": "google_places"},
    }
    key = cache_mod.make_cache_key(42.3505, -71.1054, "coffee_shop", 1.0)
    cache_mod.set(key, bundle)
    loaded = cache_mod.get(key)
    assert loaded is not None
    assert "_cache_meta" in loaded
    cm = loaded["_cache_meta"]
    assert cm["cache_hit"] is True
    assert isinstance(cm["written_at"], str) and cm["written_at"]


def test_cache_miss_meta_injected_by_live_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(live_adapter, "get", lambda key: None)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "live_bundles")
    cache_mod.init_cache_dir()

    comp = {
        "source": "google_places",
        "summary": {"total_count": 1, "avg_rating": 4.0, "top_3_review_share_pct": 10.0},
    }
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
        with patch.object(live_adapter, "fetch_competitors_with_retry", return_value=comp):
            with patch.object(live_adapter, "fetch_census_with_retry", return_value=cens):
                out = fetch_live_bundle(42.35, -71.105, "coffee_shop", radius_miles=1.0)

    assert "_cache_meta" in out
    assert out["_cache_meta"]["cache_hit"] is False


def test_cache_meta_stripped_before_scoring():
    bundle = {
        "query": {"lat": 1.0},
        "competitor_data": {},
        "_cache_meta": {
            "cache_hit": True,
            "written_at": "2026-01-01 12:00:00",
            "key": "k",
            "ttl_days": 14,
        },
    }
    clean_bundle = {k: v for k, v in bundle.items() if k != "_cache_meta"}
    assert "_cache_meta" not in clean_bundle
    assert clean_bundle == {"query": {"lat": 1.0}, "competitor_data": {}}


def test_cache_meta_key_is_consistent(isolated_cache_dir):
    bundle = {
        "query": {
            "lat": 42.3505,
            "lng": -71.1054,
            "business_type": "coffee_shop",
            "radius_miles": 1.0,
        },
    }
    key = cache_mod.make_cache_key(42.3505, -71.1054, "coffee_shop", 1.0)
    cache_mod.set(key, bundle)
    loaded = cache_mod.get(key)
    assert loaded is not None
    assert loaded["_cache_meta"]["key"] == key

    on_disk = json.loads((isolated_cache_dir / f"{key}.json").read_text(encoding="utf-8"))
    assert on_disk["_cache_meta"]["cache_key"] == key
