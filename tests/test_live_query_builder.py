from __future__ import annotations

import pytest

from pipeline.query_builder import build_query


def test_build_query_returns_fetcher_keys_with_casting():
    result = build_query("42.3505", "-71.1054", "  coffee_shop  ", "1.0")
    assert result == {
        "lat": 42.3505,
        "lng": -71.1054,
        "business_type": "coffee_shop",
        "radius_miles": 1.0,
    }
    assert isinstance(result["lat"], float)
    assert isinstance(result["lng"], float)
    assert isinstance(result["business_type"], str)
    assert isinstance(result["radius_miles"], float)


def test_build_query_includes_location_when_provided():
    result = build_query(42.35, -71.105, "coffee_shop", 1.0, location="  Boston University  ")
    assert result["location"] == "Boston University"


def test_build_query_location_none_omits_location_key():
    result = build_query(42.35, -71.105, "coffee_shop", 1.0, location=None)
    assert "location" not in result


def test_build_query_rejects_lat_out_of_range():
    with pytest.raises(ValueError, match="lat must be between -90 and 90"):
        build_query(91.0, -71.105, "coffee_shop", 1.0)
    with pytest.raises(ValueError, match="lat must be between -90 and 90"):
        build_query(-90.1, -71.105, "coffee_shop", 1.0)


def test_build_query_rejects_lng_out_of_range():
    with pytest.raises(ValueError, match="lng must be between -180 and 180"):
        build_query(42.35, 180.1, "coffee_shop", 1.0)
    with pytest.raises(ValueError, match="lng must be between -180 and 180"):
        build_query(42.35, -180.1, "coffee_shop", 1.0)


def test_build_query_rejects_non_positive_radius():
    with pytest.raises(ValueError, match="radius_miles must be greater than 0"):
        build_query(42.35, -71.105, "coffee_shop", 0.0)
    with pytest.raises(ValueError, match="radius_miles must be greater than 0"):
        build_query(42.35, -71.105, "coffee_shop", -1.0)


def test_build_query_rejects_empty_business_type():
    with pytest.raises(ValueError, match="business_type must be a non-empty string"):
        build_query(42.35, -71.105, "   ", 1.0)
    with pytest.raises(ValueError, match="business_type must be a non-empty string"):
        build_query(42.35, -71.105, "", 1.0)
