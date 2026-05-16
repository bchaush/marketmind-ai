"""
Global daily request counter.
Uses atomic file writes (same pattern as pipeline/cache.py).
Resets at midnight local time.
Thread-safe for Streamlit's single-process model.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date
from pathlib import Path

_LOCK = threading.Lock()
_COUNTER_FILE = Path("cache/rate_limit_counter.json")
DAILY_LIMIT = 50


def _load_counter() -> dict:
    try:
        data = json.loads(_COUNTER_FILE.read_text(encoding="utf-8"))
        if data.get("date") == str(date.today()):
            return data
    except Exception:
        pass
    return {"date": str(date.today()), "count": 0}


def _save_counter(data: dict) -> None:
    _COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _COUNTER_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, _COUNTER_FILE)


def check_and_increment() -> tuple[bool, int]:
    """
    Returns (allowed: bool, remaining: int).
    If allowed, increments the counter atomically.
    """
    with _LOCK:
        data = _load_counter()
        if data["count"] >= DAILY_LIMIT:
            return False, 0
        data["count"] += 1
        _save_counter(data)
        return True, DAILY_LIMIT - data["count"]


def remaining_today() -> int:
    return max(0, DAILY_LIMIT - _load_counter().get("count", 0))
