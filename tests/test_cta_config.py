"""CTA footer config (Phase 7 B2)."""

from __future__ import annotations

import config.cta_config as cc
import pytest


_EXPECTED_KEYS = frozenset(
    {"headline", "subtext", "link_label", "link_url", "secondary_label", "secondary_url"}
)


def test_recruiter_mode_returns_correct_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTA_MODE", "recruiter")
    cfg = cc.get_cta_config()
    assert frozenset(cfg.keys()) == _EXPECTED_KEYS
    assert isinstance(cfg["headline"], str) and cfg["headline"].strip() != ""
    assert cfg["secondary_label"] is None


def test_startup_mode_returns_correct_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTA_MODE", "startup")
    cfg = cc.get_cta_config()
    assert frozenset(cfg.keys()) == _EXPECTED_KEYS
    assert cfg["secondary_label"] is None
    assert cfg["secondary_url"] is None


def test_unknown_mode_defaults_to_recruiter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTA_MODE", "nonsense")
    got = cc.get_cta_config()
    monkeypatch.setenv("CTA_MODE", "recruiter")
    expected = cc.get_cta_config()
    assert got == expected
