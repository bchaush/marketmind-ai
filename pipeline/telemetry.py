"""Silent, opt-in coordinate + outcome telemetry (no PII)."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

_LOG_ROOT = Path("logs")
_TELEMETRY_FILE = _LOG_ROOT / "telemetry.jsonl"


def _append_line_utf8(line: str) -> None:
    """Append one UTF-8 line to the telemetry log (internal hook for testing)."""
    _LOG_ROOT.mkdir(parents=True, exist_ok=True)
    with _TELEMETRY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line)


def log_run(
    lat: Any,
    lng: Any,
    final_status: Any,
    confidence_score: Any,
) -> None:
    """
    Append a single telemetry record if TELEMETRY_ENABLED=true.
    Coordinates rounded to 3 decimals; failures are logged and swallowed.
    """
    if os.getenv("TELEMETRY_ENABLED", "false").strip().lower() != "true":
        return

    try:
        rlat = round(float(lat), 3)
        rlng = round(float(lng), 3)
    except (TypeError, ValueError):
        logger.warning("telemetry skipped: lat/lng not numeric")
        return

    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "ts": ts,
        "lat": rlat,
        "lng": rlng,
        "status": str(final_status),
        "confidence": confidence_score if confidence_score is None else float(confidence_score),
    }
    line = json.dumps(payload, separators=(",", ":")) + "\n"

    try:
        with _LOCK:
            _append_line_utf8(line)
    except OSError as exc:
        logger.warning("telemetry write failed (%s)", exc.__class__.__name__, exc_info=True)
