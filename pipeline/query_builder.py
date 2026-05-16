from __future__ import annotations


def build_query(
    lat: float,
    lng: float,
    business_type: str,
    radius_miles: float,
    location: str | None = None,
) -> dict:
    lat_f = float(lat)
    lng_f = float(lng)
    radius_f = float(radius_miles)
    business_type_s = str(business_type).strip()

    if lat_f < -90 or lat_f > 90:
        raise ValueError(f"lat must be between -90 and 90 (got {lat_f})")
    if lng_f < -180 or lng_f > 180:
        raise ValueError(f"lng must be between -180 and 180 (got {lng_f})")
    if radius_f <= 0:
        raise ValueError(f"radius_miles must be greater than 0 (got {radius_f})")
    if not business_type_s:
        raise ValueError("business_type must be a non-empty string")

    query: dict = {
        "lat": lat_f,
        "lng": lng_f,
        "business_type": business_type_s,
        "radius_miles": radius_f,
    }

    if location is not None:
        location_s = str(location).strip()
        if location_s:
            query["location"] = location_s

    return query
