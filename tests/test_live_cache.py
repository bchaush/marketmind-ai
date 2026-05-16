from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from pipeline import cache as live_cache


@pytest.fixture
def isolated_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cache_root = tmp_path / "live_bundles"
    monkeypatch.setattr(live_cache, "CACHE_DIR", cache_root)
    monkeypatch.setattr(live_cache, "CACHE_TTL_DAYS", 14)
    live_cache.init_cache_dir()
    yield cache_root


def test_normalize_coords_rounds_to_three_decimals():
    assert live_cache.normalize_coords(42.350499, -71.105499) == (42.350, -71.105)
    assert live_cache.normalize_coords(42.3514, -71.1056) == (42.351, -71.106)


def test_make_cache_key_uses_normalized_coords_and_slugified_type():
    key = live_cache.make_cache_key(42.350499, -71.105499, "Coffee Shop", 1.0)
    assert key == "42.35_-71.105_coffee_shop_1.0"


def test_make_cache_key_same_zone_collapses():
    k1 = live_cache.make_cache_key(42.350499, -71.105499, "coffee_shop", 1.0)
    k2 = live_cache.make_cache_key(42.3504, -71.1054, "coffee_shop", 1.0)
    assert k1 == k2
    assert k1 == "42.35_-71.105_coffee_shop_1.0"


def test_set_and_get_round_trip(isolated_cache_dir: Path):
    bundle = {
        "query": {
            "lat": 42.3505,
            "lng": -71.1054,
            "business_type": "coffee_shop",
            "radius_miles": 1.0,
        },
        "competitor_data": {"source": "google_places"},
    }
    key = live_cache.make_cache_key(42.3505, -71.1054, "coffee_shop", 1.0)
    live_cache.set(key, bundle)
    loaded = live_cache.get(key)
    assert loaded is not None
    meta = loaded.pop("_cache_meta")
    assert meta["cache_hit"] is True
    assert meta["key"] == key
    assert meta["ttl_days"] == live_cache.CACHE_TTL_DAYS
    assert isinstance(meta["written_at"], str) and meta["written_at"]
    assert loaded == bundle

    on_disk = json.loads((isolated_cache_dir / f"{key}.json").read_text(encoding="utf-8"))
    assert "_cache_meta" in on_disk
    assert on_disk["_cache_meta"]["source"] == "live_api_cache"
    assert on_disk["_cache_meta"]["cache_key"] == key


def test_get_missing_returns_none(isolated_cache_dir: Path):
    assert live_cache.get("missing_key") is None


def test_get_malformed_json_returns_none(isolated_cache_dir: Path):
    key = "bad_json_key"
    path = isolated_cache_dir / f"{key}.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert live_cache.get(key) is None


def test_get_expired_returns_none(isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(live_cache, "CACHE_TTL_DAYS", 1)
    bundle = {
        "query": {
            "lat": 42.3505,
            "lng": -71.1054,
            "business_type": "coffee_shop",
            "radius_miles": 1.0,
        }
    }
    key = live_cache.make_cache_key(42.3505, -71.1054, "coffee_shop", 1.0)
    live_cache.set(key, bundle)
    path = isolated_cache_dir / f"{key}.json"
    old = time.time() - (2 * 86400)
    os.utime(path, (old, old))
    assert live_cache.get(key) is None


def test_set_atomic_write_no_partial_file(isolated_cache_dir: Path):
    bundle = {
        "query": {
            "lat": 42.3505,
            "lng": -71.1054,
            "business_type": "coffee_shop",
            "radius_miles": 1.0,
        }
    }
    key = live_cache.make_cache_key(42.3505, -71.1054, "coffee_shop", 1.0)
    live_cache.set(key, bundle)
    assert (isolated_cache_dir / f"{key}.json").is_file()
    assert not (isolated_cache_dir / f"{key}.json.tmp").exists()
