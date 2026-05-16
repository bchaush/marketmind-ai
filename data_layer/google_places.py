from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from config.secrets import google_api_key
from dotenv import load_dotenv
from tenacity import Retrying, RetryError, retry_if_exception, stop_after_attempt, wait_exponential


BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"

FIELD_MASK = ",".join(
    [
        "places.displayName",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.location",
        "places.types",
        "places.businessStatus",
    ]
)

logger = logging.getLogger(__name__)


def load_dotenv_if_present() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def get_api_key() -> str:
    api_key = google_api_key()
    if not api_key:
        raise RuntimeError(
            "Missing Google API key. Set GOOGLE_PLACES_API_KEY (preferred) or GOOGLE_API_KEY in .env."
        )
    return api_key


def load_taxonomy() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    taxonomy_path = repo_root / "config" / "business_taxonomy.json"
    with taxonomy_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_business_config(taxonomy: Dict[str, Any], business_type: str) -> Dict[str, Any]:
    business_types = taxonomy.get("business_types") or {}
    if business_type not in business_types:
        raise KeyError(f"Unknown business_type: {business_type}")

    cfg = business_types[business_type] or {}

    required_status = cfg.get("required_status")
    excluded_types = cfg.get("excluded_types") or []
    negative_keywords = cfg.get("negative_keywords") or []
    cluster_tag_rules = cfg.get("cluster_tag_rules") or []
    chain_name_markers = cfg.get("chain_name_markers") or []

    if not isinstance(excluded_types, list):
        excluded_types = []
    if not isinstance(negative_keywords, list):
        negative_keywords = []
    if not isinstance(cluster_tag_rules, list):
        cluster_tag_rules = []
    if not isinstance(chain_name_markers, list):
        chain_name_markers = []

    return {
        **cfg,
        "required_status": required_status,
        "excluded_types": excluded_types,
        "negative_keywords": negative_keywords,
        "cluster_tag_rules": cluster_tag_rules,
        "chain_name_markers": chain_name_markers,
    }


def search_places_nearby(
    *,
    api_key: str,
    lat: float,
    lng: float,
    radius_miles: float,
    included_types: List[str],
    max_pages: int = 5,
) -> List[Dict[str, Any]]:
    radius_meters = int(max(0.1, radius_miles) * 1609.344)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    all_places: List[Dict[str, Any]] = []
    page_token: Optional[str] = None

    audit_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _should_retry(exc: BaseException) -> bool:
        if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return exc.response.status_code in (500, 502, 503)
        return False

    for page_n in range(1, max_pages + 1):
        body: Dict[str, Any] = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_meters,
                }
            }
        }

        if included_types:
            body["includedTypes"] = included_types
        if page_token:
            body["pageToken"] = page_token

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=4),
                retry=retry_if_exception(_should_retry),
                reraise=True,
            ):
                with attempt:
                    resp = requests.post(
                        BASE_URL,
                        headers=headers,
                        json=body,
                        timeout=(5, 15),
                    )
                    resp.raise_for_status()
        except RetryError as e:
            logger.exception("Google Places Nearby request failed after retries (page=%s)", page_n)
            raise e.last_attempt.exception() from e

        payload = resp.json()

        repo_root = Path(__file__).resolve().parents[1]
        raw_dir = repo_root / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"google_raw_{audit_ts}_page{page_n}.json"
        with raw_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")

        all_places.extend(extract_places_list(payload))

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

        # Token readiness can be slightly delayed.
        time.sleep(2)

    return all_places


def extract_places_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    places = payload.get("places")
    if isinstance(places, list):
        return [p for p in places if isinstance(p, dict)]
    return []


def distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    # Haversine
    r_miles = 3958.7613
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r_miles * c


def derive_category_tags(place: Dict[str, Any], business_type_config: Dict[str, Any]) -> List[str]:
    tags: List[str] = []

    name = (
        ((place.get("displayName") or {}).get("text"))
        if isinstance(place.get("displayName"), dict)
        else None
    )
    name_l = (name or "").lower()

    types = place.get("types") or []
    if not isinstance(types, list):
        types = []
    types_set = {t for t in types if isinstance(t, str)}

    price_level = place.get("priceLevel")
    price_num: Optional[int] = None
    if isinstance(price_level, int):
        price_num = price_level
    elif isinstance(price_level, str):
        try:
            price_num = int(price_level)
        except Exception:
            price_num = None

    if price_num is not None:
        if price_num >= 3:
            tags.append("premium")
        elif price_num <= 1:
            tags.append("budget")

    if "bakery" in types_set:
        tags.append("bakery-cafe")

    chain_markers = business_type_config.get("chain_name_markers") or []
    if not isinstance(chain_markers, list):
        chain_markers = []
    chain_markers_l = [m.lower() for m in chain_markers if isinstance(m, str)]
    if chain_markers_l and any(m in name_l for m in chain_markers_l):
        tags.append("chain")

    if "meal_takeaway" in types_set or "takeout" in types_set:
        tags.append("grab-and-go")

    if "roaster" in name_l or "roastery" in name_l or "specialty" in name_l:
        tags.append("specialty")

    seen = set()
    out: List[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def compute_strength_index(rating: Optional[float], review_count: Optional[int]) -> float:
    if rating is None or review_count is None or review_count <= 0:
        return 0.0
    return float(rating) * math.log10(float(review_count))


def places_row_to_competitor(
    *,
    place: Dict[str, Any],
    idx: int,
    origin_lat: float,
    origin_lng: float,
    business_type_config: Dict[str, Any],
) -> Dict[str, Any]:
    display = place.get("displayName") or {}
    name = display.get("text") if isinstance(display, dict) else None
    if not isinstance(name, str):
        name = "Unknown"

    rating_val = place.get("rating")
    rating: Optional[float]
    if isinstance(rating_val, (int, float)):
        rating = float(rating_val)
    else:
        rating = None

    urc_val = place.get("userRatingCount")
    review_count: Optional[int]
    if isinstance(urc_val, int):
        review_count = urc_val
    elif isinstance(urc_val, float) and urc_val.is_integer():
        review_count = int(urc_val)
    else:
        review_count = None

    loc = place.get("location") or {}
    lat2 = loc.get("latitude") if isinstance(loc, dict) else None
    lng2 = loc.get("longitude") if isinstance(loc, dict) else None

    if isinstance(lat2, (int, float)) and isinstance(lng2, (int, float)):
        dist = distance_miles(origin_lat, origin_lng, float(lat2), float(lng2))
    else:
        dist = 0.0

    tags = derive_category_tags(place, business_type_config)
    strength = compute_strength_index(rating, review_count)

    return {
        "id": f"comp_{idx:03d}",
        "name": name,
        "rating": rating,
        "review_count": review_count if review_count is not None else 0,
        "distance_miles": round(float(dist), 2),
        "category_tags": tags,
        "mock_strength_index": round(float(strength), 2),
    }


def build_cluster_breakdown(
    competitors: List[Dict[str, Any]], cluster_tag_rules: List[Dict[str, Any]]
) -> Dict[str, int]:
    breakdown: Dict[str, int] = {}

    for comp in competitors:
        tags = comp.get("category_tags") or []
        if not isinstance(tags, list):
            tags = []
        tags_set = {t for t in tags if isinstance(t, str)}

        matched_cluster: Optional[str] = None
        for rule in cluster_tag_rules:
            if not isinstance(rule, dict):
                continue
            cluster = rule.get("cluster")
            match_any = rule.get("match_any_category_tags") or []
            if not isinstance(cluster, str) or not isinstance(match_any, list):
                continue
            if any((isinstance(t, str) and t in tags_set) for t in match_any):
                matched_cluster = cluster
                break

        if matched_cluster:
            breakdown[matched_cluster] = breakdown.get(matched_cluster, 0) + 1

    return breakdown


def build_competitor_summary(
    competitors: List[Dict[str, Any]], cluster_breakdown: Dict[str, int]
) -> Dict[str, Any]:
    total_count = len(competitors)

    ratings = [c.get("rating") for c in competitors if isinstance(c.get("rating"), (int, float))]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    review_counts = [
        c.get("review_count") for c in competitors if isinstance(c.get("review_count"), int)
    ]
    avg_review_count = int(round(sum(review_counts) / len(review_counts))) if review_counts else 0

    total_reviews = sum(review_counts) if review_counts else 0
    top3 = sorted(review_counts, reverse=True)[:3] if review_counts else []
    top3_share = (sum(top3) / total_reviews * 100.0) if total_reviews > 0 else 0.0

    return {
        "total_count": total_count,
        "avg_rating": avg_rating,
        "avg_review_count": avg_review_count,
        "top_3_review_share_pct": round(top3_share, 1),
        "cluster_breakdown": cluster_breakdown,
    }


def fetch_competitor_data(query: Dict[str, Any]) -> Dict[str, Any]:
    load_dotenv_if_present()
    api_key = get_api_key()

    taxonomy = load_taxonomy()
    business_type = query.get("business_type")
    if not isinstance(business_type, str):
        raise ValueError("query.business_type must be a string")

    cfg = get_business_config(taxonomy, business_type)

    lat = float(query.get("lat"))
    lng = float(query.get("lng"))
    radius_miles = float(query.get("radius_miles", cfg.get("default_radius_miles", 1.0)))

    required_status = cfg.get("required_status")
    excluded_types = set(t for t in (cfg.get("excluded_types") or []) if isinstance(t, str))
    negative_keywords = [
        k.lower() for k in (cfg.get("negative_keywords") or []) if isinstance(k, str)
    ]
    cluster_tag_rules = cfg.get("cluster_tag_rules") or []

    included_types = cfg.get("places_types_hint") or []
    if not isinstance(included_types, list):
        included_types = []

    raw_places = search_places_nearby(
        api_key=api_key,
        lat=lat,
        lng=lng,
        radius_miles=radius_miles,
        included_types=[t for t in included_types if isinstance(t, str)],
        max_pages=5,
    )

    filtered_places: List[Dict[str, Any]] = []
    for p in raw_places:
        # required_status filter BEFORE mapping any result
        bs = p.get("businessStatus")
        if required_status and bs != required_status:
            continue

        types = p.get("types") or []
        if not isinstance(types, list):
            types = []
        if excluded_types and any((isinstance(t, str) and t in excluded_types) for t in types):
            continue

        display = p.get("displayName") or {}
        name = display.get("text") if isinstance(display, dict) else ""
        name_l = name.lower() if isinstance(name, str) else ""
        if negative_keywords and any(kw in name_l for kw in negative_keywords):
            continue

        filtered_places.append(p)

    competitors: List[Dict[str, Any]] = []
    for i, place in enumerate(filtered_places, start=1):
        competitors.append(
            places_row_to_competitor(
                place=place,
                idx=i,
                origin_lat=lat,
                origin_lng=lng,
                business_type_config=cfg,
            )
        )

    cluster_breakdown = build_cluster_breakdown(competitors, cluster_tag_rules)
    summary = build_competitor_summary(competitors, cluster_breakdown)

    confidence_level = "HIGH" if competitors else "LOW"
    confidence_score = 90 if competitors else 30

    return {
        "source": "google_places",
        "confidence_level": confidence_level,
        "confidence_score": confidence_score,
        "radius_used_miles": radius_miles,
        "competitors": competitors,
        "summary": summary,
    }

