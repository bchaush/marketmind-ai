"""Charles River / zero-density guard — live_adapter only."""

from __future__ import annotations

import pytest

import pipeline.live_adapter as live_adapter


def _bundle(pop_total: int | None, total_count: int | None) -> dict:
    return {
        "query": {},
        "competitor_data": {"summary": {"total_count": total_count}},
        "demographic_data": {"pop_total": pop_total},
        "location_signals": {},
        "data_quality": {},
        "phase_1_validation": {},
    }


def test_zero_density_raises_when_both_empty() -> None:
    with pytest.raises(live_adapter.ZeroDensityLocationError) as excinfo:
        live_adapter._enforce_zero_density_or_raise(_bundle(0, 0))
    assert str(excinfo.value) == live_adapter.ZERO_DENSITY_USER_MESSAGE


def test_zero_density_not_raised_when_google_has_competitors() -> None:
    live_adapter._enforce_zero_density_or_raise(_bundle(0, 5))


def test_zero_density_not_raised_when_census_has_population() -> None:
    live_adapter._enforce_zero_density_or_raise(_bundle(3000, 0))
