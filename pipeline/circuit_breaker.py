from __future__ import annotations

import copy
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from data_layer.census_api import fetch_census_demographics
from data_layer.google_places import fetch_competitor_data

logger = logging.getLogger(__name__)

_GOOGLE_FAILURE_STUB: dict[str, Any] = {
    "source": "google_places",
    "summary": {
        "total_count": None,
        "avg_rating": None,
        "top_3_review_share_pct": None,
    },
}

_CENSUS_FAILURE_STUB: dict[str, Any] = {
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

_RETRY_STOP = stop_after_attempt(3)
_RETRY_WAIT = wait_exponential(multiplier=1, min=1, max=8)


@retry(stop=_RETRY_STOP, wait=_RETRY_WAIT, reraise=True)
def _fetch_competitor_data_attempt(query: dict) -> dict:
    return fetch_competitor_data(query)


@retry(stop=_RETRY_STOP, wait=_RETRY_WAIT, reraise=True)
def _fetch_census_demographics_attempt(query: dict) -> dict:
    model = fetch_census_demographics(query)
    data = model.model_dump()
    fallback_used = data.get("fallback_used")
    if not isinstance(fallback_used, list):
        fallback_used = [] if fallback_used is None else list(fallback_used)
    return {
        "source": "census_acs5",
        "pop_total": data.get("pop_total"),
        "age_22_34_count": data.get("age_22_34_count"),
        "median_household_income": data.get("median_household_income"),
        "college_student_population_pct": data.get("college_student_population_pct"),
        "rent_to_income_ratio": data.get("rent_to_income_ratio"),
        "geography_level": data.get("geography_level"),
        "confidence_score": data.get("confidence_score"),
        "fallback_used": fallback_used,
    }


def fetch_competitors_with_retry(query: dict) -> dict:
    try:
        return _fetch_competitor_data_attempt(query)
    except Exception as exc:
        logger.warning(
            "Google Places fetch failed after 3 attempts; returning degraded stub: %s",
            exc,
            exc_info=True,
        )
        return copy.deepcopy(_GOOGLE_FAILURE_STUB)


def fetch_census_with_retry(query: dict) -> dict:
    try:
        return _fetch_census_demographics_attempt(query)
    except Exception as exc:
        logger.warning(
            "Census fetch failed after 3 attempts; returning degraded stub: %s",
            exc,
            exc_info=True,
        )
        return copy.deepcopy(_CENSUS_FAILURE_STUB)
