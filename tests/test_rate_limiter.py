"""Tests for pipeline.rate_limiter (isolated counter file via monkeypatch)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import pipeline.rate_limiter as rl


@pytest.fixture
def counter_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    p = tmp_path / "rate_limit_counter.json"
    monkeypatch.setattr(rl, "_COUNTER_FILE", p)
    return p


def test_first_request_allowed(counter_path: Path) -> None:
    if counter_path.exists():
        counter_path.unlink()
    allowed, remaining = rl.check_and_increment()
    assert allowed is True
    assert remaining == 49


def test_limit_enforced(counter_path: Path) -> None:
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    counter_path.write_text(
        json.dumps({"date": str(date.today()), "count": 50}), encoding="utf-8"
    )
    allowed, remaining = rl.check_and_increment()
    assert allowed is False
    assert remaining == 0


def test_counter_resets_on_new_day(counter_path: Path) -> None:
    yesterday = date.today() - timedelta(days=1)
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    counter_path.write_text(
        json.dumps({"date": str(yesterday), "count": 50}), encoding="utf-8"
    )
    allowed, remaining = rl.check_and_increment()
    assert allowed is True
    assert remaining == 49


def test_remaining_today_accurate(counter_path: Path) -> None:
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    counter_path.write_text(
        json.dumps({"date": str(date.today()), "count": 20}), encoding="utf-8"
    )
    assert rl.remaining_today() == 30
