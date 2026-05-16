from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from decision_engine.analyst_payload import build_analyst_payload
from decision_engine.payload_schema import validate_analyst_payload
from report_engine.llm_analyst import generate_report
from scoring_engine.scoring_engine import score
from ui.payload_adapter import adapt

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
        validated_payload = validate_analyst_payload(raw)
        ui_payload = adapt(validated_payload)
        report, _used = generate_report(ui_payload)
        print(report.model_dump_json(indent=2))
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
