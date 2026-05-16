from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

CACHE_TTL_DAYS = 14
CACHE_DIR = Path("cache/live_bundles")


def init_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def normalize_coords(lat: float, lng: float) -> tuple[float, float]:
    return (round(float(lat), 3), round(float(lng), 3))


def _slugify_business_type(business_type: str) -> str:
    slug = business_type.lower().strip()
    slug = re.sub(r"[\s\-]+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "unknown"


def make_cache_key(lat: float, lng: float, business_type: str, radius_miles: float) -> str:
    lat_r, lng_r = normalize_coords(lat, lng)
    slug = _slugify_business_type(business_type)
    radius = float(radius_miles)
    return f"{lat_r}_{lng_r}_{slug}_{radius}"


def get(cache_key: str) -> dict | None:
    path = CACHE_DIR / f"{cache_key}.json"
    if not path.is_file():
        return None

    try:
        age_seconds = time.time() - path.stat().st_mtime
        if age_seconds > CACHE_TTL_DAYS * 86400:
            return None
    except OSError:
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    bundle = dict(data)
    bundle.pop("_cache_meta", None)
    bundle["_cache_meta"] = {
        "cache_hit": True,
        "written_at": datetime.fromtimestamp(path.stat().st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "key": cache_key,
        "ttl_days": CACHE_TTL_DAYS,
    }
    return bundle


def set(cache_key: str, bundle: dict) -> None:
    init_cache_dir()
    path = CACHE_DIR / f"{cache_key}.json"
    tmp_path = CACHE_DIR / f"{cache_key}.json.tmp"

    lat_r: float | None = None
    lng_r: float | None = None
    business_type = ""
    query = bundle.get("query")
    if isinstance(query, dict):
        try:
            lat_r, lng_r = normalize_coords(query["lat"], query["lng"])
            business_type = str(query.get("business_type") or "")
        except (KeyError, TypeError, ValueError):
            pass

    to_write = dict(bundle)
    to_write.pop("_cache_meta", None)
    to_write["_cache_meta"] = {
        "cache_key": cache_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lat_rounded": lat_r,
        "lng_rounded": lng_r,
        "business_type": business_type,
        "source": "live_api_cache",
    }

    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(to_write, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except OSError:
        try:
            if tmp_path.is_file():
                tmp_path.unlink()
        except OSError:
            pass
        raise


init_cache_dir()
