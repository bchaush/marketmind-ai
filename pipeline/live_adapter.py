from __future__ import annotations

import copy
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime

from data_layer.google_places import distance_miles

import pipeline.circuit_breaker as circuit_breaker_module
from pipeline.bundle_assembler import assemble
from pipeline.cache import CACHE_TTL_DAYS, get, make_cache_key, set
from pipeline.circuit_breaker import fetch_census_with_retry, fetch_competitors_with_retry
from pipeline.query_builder import build_query

logger = logging.getLogger(__name__)

ZERO_DENSITY_USER_MESSAGE = (
    "Selected coordinates appear to be in a non-commercial or zero-density area "
    "(e.g. water, park, or industrial zone). Please select a location within "
    "a commercial district."
)


class ZeroDensityLocationError(Exception):
    """Bundle represents a genuinely non-viable, zero-density location."""

INMAN_SQUARE_LAT = 42.3736
INMAN_SQUARE_LNG = -71.1097
MAX_GEOFENCE_MILES = 3.5
_FETCH_TIMEOUT_SEC = 20.0


def _fetch_google(query: dict) -> dict:
    """Run Google Places fetch in a worker thread; degradation matches circuit_breaker."""
    try:
        return fetch_competitors_with_retry(query)
    except Exception as exc:
        logger.warning(
            "Google Places parallel fetch raised unexpectedly; returning degraded stub: %s",
            exc,
            exc_info=True,
        )
        return copy.deepcopy(circuit_breaker_module._GOOGLE_FAILURE_STUB)


def _fetch_census(query: dict) -> dict:
    """Run Census fetch in a worker thread; degradation matches circuit_breaker."""
    try:
        return fetch_census_with_retry(query)
    except Exception as exc:
        logger.warning(
            "Census parallel fetch raised unexpectedly; returning degraded stub: %s",
            exc,
            exc_info=True,
        )
        return copy.deepcopy(circuit_breaker_module._CENSUS_FAILURE_STUB)


def _enforce_zero_density_or_raise(bundle: dict) -> None:
    """
    If Census shows no population and Google reports exactly zero competitors,
    the location is treated as non-commercial — do not send downstream.
    total_count None (e.g. API failure stub) is not treated as zero competitors.
    """
    demo = bundle.get("demographic_data") if isinstance(bundle.get("demographic_data"), dict) else {}
    pop_total = demo.get("pop_total")
    if pop_total is not None and pop_total != 0:
        return

    comp = bundle.get("competitor_data") if isinstance(bundle.get("competitor_data"), dict) else {}
    summary = comp.get("summary") if isinstance(comp.get("summary"), dict) else {}
    total_count = summary.get("total_count")
    if total_count != 0:
        return

    raise ZeroDensityLocationError(ZERO_DENSITY_USER_MESSAGE)


def fetch_live_bundle(
    lat: float,
    lng: float,
    business_type: str,
    *,
    radius_miles: float = 1.0,
    location: str | None = None,
) -> dict:
    query = build_query(lat, lng, business_type, radius_miles, location)
    cache_key = make_cache_key(lat, lng, business_type, radius_miles)

    cached = get(cache_key)
    if cached is not None:
        logger.debug("Cache hit for key: %s", cache_key)
        _enforce_zero_density_or_raise(cached)
        return cached

    dist = distance_miles(lat, lng, INMAN_SQUARE_LAT, INMAN_SQUARE_LNG)
    if dist > MAX_GEOFENCE_MILES:
        logger.warning(
            "Geofence rejection: (%.4f, %.4f) is %.2f miles from anchor",
            lat,
            lng,
            dist,
        )
        raise ValueError(
            "Location is outside the supported Boston area (max 3.5 miles from Inman Square)"
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_google = executor.submit(_fetch_google, query)
        fut_census = executor.submit(_fetch_census, query)
        try:
            competitor_raw = fut_google.result(timeout=_FETCH_TIMEOUT_SEC)
        except FuturesTimeoutError:
            logger.warning(
                "Google Places fetch exceeded %.0fs timeout; returning degraded stub",
                _FETCH_TIMEOUT_SEC,
            )
            competitor_raw = copy.deepcopy(circuit_breaker_module._GOOGLE_FAILURE_STUB)
        try:
            census_raw = fut_census.result(timeout=_FETCH_TIMEOUT_SEC)
        except FuturesTimeoutError:
            logger.warning(
                "Census fetch exceeded %.0fs timeout; returning degraded stub",
                _FETCH_TIMEOUT_SEC,
            )
            census_raw = copy.deepcopy(circuit_breaker_module._CENSUS_FAILURE_STUB)

    bundle = assemble(query, competitor_raw, census_raw)
    _enforce_zero_density_or_raise(bundle)
    set(cache_key, bundle)
    logger.debug("Cache miss — bundle fetched and cached for key: %s", cache_key)
    out = dict(bundle)
    out["_cache_meta"] = {
        "cache_hit": False,
        "written_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "key": cache_key,
        "ttl_days": CACHE_TTL_DAYS,
    }
    return out
