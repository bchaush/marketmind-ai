from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from tenacity import wait_exponential

from pipeline.circuit_breaker import (
    _CENSUS_FAILURE_STUB,
    _GOOGLE_FAILURE_STUB,
    fetch_census_with_retry,
    fetch_competitors_with_retry,
)


@pytest.fixture()
def no_retry_wait(monkeypatch):
    monkeypatch.setattr(
        "pipeline.circuit_breaker._RETRY_WAIT",
        wait_exponential(multiplier=0, min=0, max=0),
    )


def test_fetch_competitors_success_returns_api_result():
    expected = {
        "source": "google_places",
        "summary": {
            "total_count": 12,
            "avg_rating": 4.2,
            "top_3_review_share_pct": 40.0,
        },
        "competitors": [],
    }
    with patch(
        "pipeline.circuit_breaker.fetch_competitor_data",
        return_value=expected,
    ) as mock_fetch:
        result = fetch_competitors_with_retry({"lat": 42.35, "lng": -71.105})
    assert result == expected
    assert mock_fetch.call_count == 1


def test_fetch_competitors_failure_returns_stub_never_raises(no_retry_wait):
    with patch(
        "pipeline.circuit_breaker.fetch_competitor_data",
        side_effect=RuntimeError("api down"),
    ) as mock_fetch:
        result = fetch_competitors_with_retry({"lat": 42.35, "lng": -71.105})
    assert result == _GOOGLE_FAILURE_STUB
    assert mock_fetch.call_count == 3


def test_fetch_census_success_returns_normalized_dict():
    model = MagicMock()
    model.model_dump.return_value = {
        "pop_total": 1542,
        "age_22_34_count": 158,
        "median_household_income": 72000,
        "college_student_population_pct": 12.5,
        "rent_to_income_ratio": 28.0,
        "geography_level": "block_group",
        "confidence_score": 100,
        "fallback_used": [],
    }
    with patch(
        "pipeline.circuit_breaker.fetch_census_demographics",
        return_value=model,
    ) as mock_fetch:
        result = fetch_census_with_retry({"lat": 42.35, "lng": -71.105})
    assert result["source"] == "census_acs5"
    assert result["pop_total"] == 1542
    assert result["geography_level"] == "block_group"
    assert mock_fetch.call_count == 1


def test_fetch_census_failure_returns_stub_never_raises(no_retry_wait):
    with patch(
        "pipeline.circuit_breaker.fetch_census_demographics",
        side_effect=ValueError("census down"),
    ) as mock_fetch:
        result = fetch_census_with_retry({"lat": 42.35, "lng": -71.105})
    assert result == _CENSUS_FAILURE_STUB
    assert mock_fetch.call_count == 3


def test_google_and_census_failures_are_independent(no_retry_wait):
    census_model = MagicMock()
    census_model.model_dump.return_value = {
        "pop_total": 100,
        "age_22_34_count": 10,
        "median_household_income": None,
        "college_student_population_pct": None,
        "rent_to_income_ratio": None,
        "geography_level": "tract",
        "confidence_score": 90,
        "fallback_used": [],
    }
    with patch(
        "pipeline.circuit_breaker.fetch_competitor_data",
        side_effect=RuntimeError("google down"),
    ), patch(
        "pipeline.circuit_breaker.fetch_census_demographics",
        return_value=census_model,
    ) as mock_census:
        comp = fetch_competitors_with_retry({"lat": 42.35, "lng": -71.105})
        demo = fetch_census_with_retry({"lat": 42.35, "lng": -71.105})
    assert comp == _GOOGLE_FAILURE_STUB
    assert demo["geography_level"] == "tract"
    assert mock_census.call_count == 1
