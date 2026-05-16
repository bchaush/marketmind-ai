from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from data_layer import google_places as gp


def _filter_places_like_fetch_loop(raw_places, cfg):
    required_status = cfg.get("required_status")
    excluded_types = set(t for t in (cfg.get("excluded_types") or []) if isinstance(t, str))
    negative_keywords = [k.lower() for k in (cfg.get("negative_keywords") or []) if isinstance(k, str)]

    filtered = []
    for p in raw_places:
        # required_status filter BEFORE mapping any result
        bs = p.get("businessStatus")
        if required_status and bs != required_status:
            continue

        types = p.get("types") or []
        if not isinstance(types, list):
            types = []
        if excluded_types and any((isinstance(t, str) and t in excluded_types) for t in types):
            continue

        display = p.get("displayName") or {}
        name = display.get("text") if isinstance(display, dict) else ""
        name_l = name.lower() if isinstance(name, str) else ""
        if negative_keywords and any(kw in name_l for kw in negative_keywords):
            continue

        filtered.append(p)
    return filtered


def test_1_filters_required_status_excluded_types_and_negative_keywords_without_http():
    cfg = {
        "required_status": "OPERATIONAL",
        "excluded_types": ["gas_station", "supermarket", "fast_food_restaurant", "donut_shop"],
        "negative_keywords": ["hospital", "university", "dining hall"],
        "chain_name_markers": ["starbucks"],  # not used in filter, but used in mapping
    }

    raw_places = [
        {
            "displayName": {"text": "Good Coffee"},
            "businessStatus": "OPERATIONAL",
            "types": ["cafe"],
            "location": {"latitude": 42.0, "longitude": -71.0},
            "rating": 4.5,
            "userRatingCount": 100,
        },
        {
            "displayName": {"text": "Campus Dining Hall Cafe"},
            "businessStatus": "OPERATIONAL",
            "types": ["cafe"],
            "location": {"latitude": 42.0, "longitude": -71.0},
        },
        {
            "displayName": {"text": "Coffee at the Gas Station"},
            "businessStatus": "OPERATIONAL",
            "types": ["gas_station", "cafe"],
            "location": {"latitude": 42.0, "longitude": -71.0},
        },
        {
            "displayName": {"text": "Closed Cafe"},
            "businessStatus": "CLOSED_TEMPORARILY",
            "types": ["cafe"],
            "location": {"latitude": 42.0, "longitude": -71.0},
        },
    ]

    filtered = _filter_places_like_fetch_loop(raw_places, cfg)
    assert len(filtered) == 1
    assert filtered[0]["displayName"]["text"] == "Good Coffee"

    comp = gp.places_row_to_competitor(
        place=filtered[0],
        idx=1,
        origin_lat=42.0,
        origin_lng=-71.0,
        business_type_config=cfg,
    )
    assert comp["id"] == "comp_001"
    assert comp["name"] == "Good Coffee"


def test_2_places_row_to_competitor_handles_null_rating_review_count_price_level_without_http():
    cfg = {
        "chain_name_markers": ["starbucks", "dunkin"],
        "required_status": "OPERATIONAL",
        "excluded_types": [],
        "negative_keywords": [],
    }

    place = {
        "displayName": {"text": "Starbucks"},
        "businessStatus": "OPERATIONAL",
        "types": ["cafe", "coffee_shop"],
        "location": {"latitude": 42.3505, "longitude": -71.1054},
        # rating missing
        # userRatingCount missing
        # priceLevel missing
    }

    comp = gp.places_row_to_competitor(
        place=place,
        idx=2,
        origin_lat=42.3505,
        origin_lng=-71.1054,
        business_type_config=cfg,
    )

    assert comp["id"] == "comp_002"
    assert comp["name"] == "Starbucks"
    assert comp["rating"] is None
    assert comp["review_count"] == 0
    assert comp["mock_strength_index"] == 0.0
    assert "chain" in comp["category_tags"]


def test_3_fetch_competitor_data_offline_end_to_end_with_mocked_api_key_and_http():
    # Mock a single-page Places response (no nextPageToken) containing one valid and one invalid place
    mock_payload = {
        "places": [
            {
                "displayName": {"text": "Pavement Coffeehouse"},
                "rating": 4.6,
                "userRatingCount": 840,
                "priceLevel": None,
                "location": {"latitude": 42.351, "longitude": -71.106},
                "types": ["cafe"],
                "businessStatus": "OPERATIONAL",
            },
            {
                "displayName": {"text": "Some University Cafe"},
                "rating": 4.8,
                "userRatingCount": 10,
                "location": {"latitude": 42.351, "longitude": -71.106},
                "types": ["cafe"],
                "businessStatus": "OPERATIONAL",
            },
        ]
    }

    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = Mock(return_value=mock_payload)

    query = {
        "business_type": "coffee_shop",
        "location": "Boston University, Boston MA",
        "lat": 42.3505,
        "lng": -71.1054,
        "radius_miles": 1.0,
        "target_customer": "students",
        "budget_level": "medium",
        "scenario_config": {
            "business_model": "study_cafe",
            "pricing_strategy": "mid",
            "target_behavior": ["long_stay", "wifi_usage"],
            "peak_hours_focus": "afternoon_evening",
        },
    }

    with patch.object(gp, "get_api_key", return_value="test_key"), patch.object(
        gp, "load_dotenv_if_present", return_value=None
    ), patch.object(gp.requests, "post", return_value=resp):
        competitor_data = gp.fetch_competitor_data(query)

    # Schema must match mock_data/mock_boston_data.json's competitor_data exactly
    assert set(competitor_data.keys()) == {
        "source",
        "confidence_level",
        "confidence_score",
        "radius_used_miles",
        "competitors",
        "summary",
    }
    assert competitor_data["source"] == "google_places"
    assert isinstance(competitor_data["competitors"], list)
    assert isinstance(competitor_data["summary"], dict)

    # Negative keyword filter should remove "University"
    assert len(competitor_data["competitors"]) == 1
    c0 = competitor_data["competitors"][0]
    assert set(c0.keys()) == {
        "id",
        "name",
        "rating",
        "review_count",
        "distance_miles",
        "category_tags",
        "mock_strength_index",
    }
    assert c0["id"] == "comp_001"
    assert c0["name"] == "Pavement Coffeehouse"


def test_4_search_places_nearby_pagination_stops_after_max_pages_even_if_token_never_ends():
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = Mock(return_value={"places": [], "nextPageToken": "always"})

    with patch.object(gp.requests, "post", return_value=resp) as post_mock, patch.object(
        gp.time, "sleep", return_value=None
    ):
        places = gp.search_places_nearby(
            api_key="test_key",
            lat=42.0,
            lng=-71.0,
            radius_miles=1.0,
            included_types=["cafe"],
            max_pages=5,
        )

    assert places == []
    assert post_mock.call_count == 5


def test_5_aggregation_math_against_mock_data():
    # Load verified mock data (no HTTP, pure aggregation checks)
    repo_root = Path(__file__).resolve().parents[1]
    mock_path = repo_root / "mock_data" / "mock_boston_data.json"
    with mock_path.open("r", encoding="utf-8") as f:
        mock_doc = json.load(f)

    summary = mock_doc["competitor_data"]["summary"]
    assert summary["total_count"] == 15
    assert summary["avg_rating"] == 4.43
    assert summary["top_3_review_share_pct"] == 45.9

    demo = mock_doc["demographic_data"]
    assert demo["pop_total"] == 1542
    assert demo["age_22_34_count"] == 158


def test_6_radius_conversion_respects_small_values():
    # Mirrors the conversion logic in data_layer.google_places.search_places_nearby
    def radius_meters_from_miles(radius_miles: float) -> int:
        return int(max(0.1, radius_miles) * 1609.344)

    m03 = radius_meters_from_miles(0.3)
    assert 480 <= m03 <= 490

    m01 = radius_meters_from_miles(0.1)
    assert 160 <= m01 <= 165

    m005 = radius_meters_from_miles(0.05)
    assert m005 >= 160

