from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import validate_analyst_payload
from scoring_engine.scoring_engine import score

MOCK_PATH = REPO_ROOT / "mock_data" / "mock_boston_data.json"
SCORE_KEYS = (
    "demand_score",
    "competition_pressure_score",
    "market_gap_score",
    "risk_score",
    "opportunity_score",
    "confidence_score",
)


def main() -> None:
    try:
        bundle = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
        phase2 = score(bundle)
        scores = {k: phase2[k] for k in SCORE_KEYS}
        flags = list(phase2["flags"])
        raw = build_analyst_payload(scores, flags)
        validated = validate_analyst_payload(raw)
        print("Backend Pipeline Verified Successfully.")
        print(validated.model_dump_json(indent=2))
        from ui.payload_adapter import adapt
        ui_payload = adapt(validated)
        print("\n--- ADAPTER OUTPUT ---")
        print(json.dumps(ui_payload, indent=2, default=str))
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
