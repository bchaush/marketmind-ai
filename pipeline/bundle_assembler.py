from __future__ import annotations

import copy


def assemble(query: dict, competitor_raw: dict, census_raw: dict) -> dict:
    google_live = competitor_raw.get("summary", {}).get("total_count") is not None
    census_live = census_raw.get("pop_total") is not None

    return {
        "query": copy.deepcopy(query),
        "competitor_data": copy.deepcopy(competitor_raw),
        "demographic_data": copy.deepcopy(census_raw),
        "location_signals": {},
        "data_quality": {
            "google_live": google_live,
            "census_live": census_live,
        },
        "phase_1_validation": {
            "passed": True,
            "google_data_present": google_live,
            "census_data_present": census_live,
        },
    }
