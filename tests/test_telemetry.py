"""Tests for pipeline.telemetry (silent JSONL telemetry)."""

from __future__ import annotations

import json

import pytest

import pipeline.telemetry as telem


@pytest.fixture(autouse=True)
def _clear_telemetry_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEMETRY_ENABLED", raising=False)


def test_log_run_disabled_creates_no_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("TELEMETRY_ENABLED", raising=False)
    monkeypatch.chdir(tmp_path)
    telem.log_run(1.23456789, -2.87654321, "GO", 50.0)
    assert not (tmp_path / "logs" / "telemetry.jsonl").exists()


def test_log_run_enabled_writes_correct_fields(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TELEMETRY_ENABLED", "true")
    monkeypatch.setattr(telem, "_LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(telem, "_TELEMETRY_FILE", tmp_path / "logs" / "telemetry.jsonl")
    telem.log_run(42.373612, -71.109734, "CAUTION", 92.0)
    p = tmp_path / "logs" / "telemetry.jsonl"
    assert p.is_file()
    line = p.read_text(encoding="utf-8").strip().splitlines()[-1]
    record = json.loads(line)
    assert record["lat"] == pytest.approx(42.374)
    assert record["lng"] == pytest.approx(-71.11)
    assert record["status"] == "CAUTION"
    assert record["confidence"] == pytest.approx(92.0)
    assert "ts" in record and isinstance(record["ts"], str) and record["ts"]


def test_log_run_coordinates_never_exceed_3dp(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TELEMETRY_ENABLED", "true")
    monkeypatch.setattr(telem, "_LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(telem, "_TELEMETRY_FILE", tmp_path / "logs" / "telemetry.jsonl")

    precise_lat = 10.987654321
    precise_lng = -20.987654321
    telem.log_run(precise_lat, precise_lng, "GO", None)

    p = tmp_path / "logs" / "telemetry.jsonl"
    record = json.loads(p.read_text(encoding="utf-8").strip())

    def frac_len(v: float) -> int:
        s = str(v)
        if "." not in s:
            return 0
        return len(s.split(".")[-1])

    assert frac_len(record["lat"]) <= 3
    assert frac_len(record["lng"]) <= 3


def test_log_run_oserror_does_not_raise(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TELEMETRY_ENABLED", "true")
    monkeypatch.setattr(telem, "_LOG_ROOT", tmp_path / "logs")
    monkeypatch.setattr(telem, "_TELEMETRY_FILE", tmp_path / "logs" / "telemetry.jsonl")

    def raise_os_err(_line: str) -> None:
        raise OSError("simulated telemetry failure")

    monkeypatch.setattr(telem, "_append_line_utf8", raise_os_err)
    telem.log_run(1.0, 2.0, "GO", 10.0)  # should not propagate
