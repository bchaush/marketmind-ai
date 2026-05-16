"""
Utility: clear all on-disk pipeline cache files.
Run this after changing default coordinates or during testing to ensure you are
seeing live data, not stale 14-day cached bundles.

Usage: python scripts/clear_demo_cache.py
"""

from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.cache import CACHE_DIR, init_cache_dir  # noqa: E402


def clear_cache() -> None:
    init_cache_dir()
    cache_dir = Path(CACHE_DIR)
    files = sorted(cache_dir.glob("*.json"))
    if not files:
        print("Cache is already empty.")
        return
    for f in files:
        f.unlink()
        print(f"Deleted: {f}")
    print(f"Cleared {len(files)} cache file(s).")


if __name__ == "__main__":
    clear_cache()
