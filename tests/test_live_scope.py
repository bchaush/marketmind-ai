"""Live UI is locked to coffee_shop only."""

from __future__ import annotations

from pathlib import Path

from ui.live_scope import LIVE_BUSINESS_TYPE, get_live_business_type


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_get_live_business_type_is_coffee_shop() -> None:
    assert LIVE_BUSINESS_TYPE == "coffee_shop"
    assert get_live_business_type() == "coffee_shop"


def test_app_has_no_free_text_business_type_input() -> None:
    src = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.text_input("Business type"' not in src
    assert "get_live_business_type" in src
    assert "**Business type:** Coffee shop" in src


def test_app_uses_data_confidence_label() -> None:
    src = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert 'metric("Data Confidence"' in src
    assert 'metric("Confidence Score"' not in src
    assert "not predictive certainty" in src
