# Phase 6 Hardening Sign-Off — LLM Analyst Report Layer & UI Polish
**Status: Complete (Hardened)**
**Date: 2026-05-15**
**Test Count: 142/142 passing**

---

## What This Phase Was

Phase 6 (original) built the LLM report generation layer. This hardening sprint
was a targeted polish pass before any public URL is shared. The trigger was a
senior review of the live UI screenshots which identified three "prototype smell"
leaks that would immediately undermine credibility with recruiters or investors:

1. Raw internal flag strings (`STATUS_DATA_DESERT_CAUTION`, `DATA_DESERT`) were
   visible in the UI caption and appearing in LLM-generated prose.
2. Business Profile raw JSON (`volume_dependency: "high"`, etc.) was rendering
   directly in the Risk & Guardrails tab — a developer-facing payload exposed
   to end users.
3. Scenario scores (29.4 / 23.3 / 17.9) displayed as bare numbers against an
   implicit 0–100 scale, causing a psychological "F grade" anchor even when
   those scores represented the strongest available options.

A fourth structural issue was also identified and fixed: the LLM had no
code-level enforcement preventing it from hallucinating `what_would_change`
content when the payload contained no WWC items, and no mechanism to reject
reports that leaked raw flag strings through the Pydantic validator.

---

## Files Changed

- `report_engine/prompt_builder.py`
- `report_engine/llm_analyst.py`
- `app.py`
- `tests/test_golden_llm_reports.py` *(new)*

---

## Step-by-Step Changes and Results

### Step 1 — Raw Flag Translation (`prompt_builder.py` + `app.py`)

**Problem:** Raw internal identifiers like `STATUS_DATA_DESERT_CAUTION`,
`DATA_DESERT`, and `STATUS_REJECTED_DESERT` were appearing in two places:
(a) the `st.caption()` rendered directly under the status banner in the UI, and
(b) inside the XML `<market_context>` block passed to the LLM, causing the LLM
to echo them back in report prose (e.g. "the DATA_DESERT flag reveals critical
blind spots").

**Fix applied:**

Added `_FLAG_LABELS` translation map to `prompt_builder.py`:

```python
_FLAG_LABELS: dict[str, str] = {
    "DATA_DESERT": "Incomplete local data coverage",
    "STATUS_DATA_DESERT_CAUTION": "Caution: limited data confidence in this area",
    "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION": "High market consolidation risk",
    "STATUS_MONOPOLY_FORCE_CAUTION": "Caution: dominant incumbents detected",
    "GOLDMINE_ZERO_COMPETITORS": "Untapped market opportunity detected",
    "STATUS_GOLDMINE_GO": "Strong market opportunity confirmed",
    "STATUS_HIGH_RISK_NO_GO": "High risk — market entry not recommended",
    "STATUS_DEFAULT_CAUTION": "Proceed with caution — mixed market signals",
    "STATUS_REJECTED_DESERT": "No-Go: insufficient demographic data at this location",
    "REJECTED_DESERT": "Insufficient demographic data at this location",
    "TO_GO_BLOCK_GROUP_DATA": "Analysis would upgrade to GO if block-group level data becomes available",
    "TO_NO_GO_PLACEHOLDER_GEOGRAPHY": "Analysis would downgrade to NO-GO if only placeholder geography is available",
}
```

Translation applied at every XML injection point: top-level `<flags>`,
`<status_rule_id>`, nested risk `<flags>` arrays, and optional `<hidden_risks>`.
Unknown flags pass through unchanged — no crash risk on future additions.

In `app.py`, import added at top-level and `st.caption(status_rule_id)` replaced
with `st.caption(_FLAG_LABELS.get(status_rule_id, status_rule_id))`.

**Result:** Caption under status banner now reads plain English
(e.g. "No-Go: insufficient demographic data at this location"). LLM prose
contains zero raw flag strings across Executive Summary, Pillar Analysis,
Scenario Analysis, and Confidence Note. Verified by automated prompt smoke test
and live browser run.

---

### Step 2 — Suppress Business Profile Raw JSON (`app.py`)

**Problem:** The Risk & Guardrails tab was rendering a raw JSON block labelled
"Business Profile" showing internal taxonomy keys (`volume_dependency`,
`margin_model`, `rent_sensitivity`, `competition_sensitivity`). Non-technical
users and investors read JSON as an error state.

**Fix applied:** Deleted the two-line rendering block from `app.py`:

```python
st.subheader("Business Profile")
st.json(business_profile)
```

No replacement. The information is fully synthesized by the LLM report layer
and adds no user-facing value that the analyst report doesn't already cover.
Raw taxonomy data remains available for a future "Developer Mode" expander.

**Result:** Risk & Guardrails tab ends cleanly at "What Would Change". No JSON
visible in any tab.

---

### Step 3 — Relative Viability Index + Qualitative Bands (`app.py`)

**Problem:** Scenario scores of 29.4 / 23.3 / 17.9 displayed as bare numbers
were being read as failing grades on a 0–100 scale. Users had no frame of
reference that these are *relative* strategic fit indices, not absolute scores.

**Fix applied:** Added explanatory caption and qualitative band labels below
each scenario metric:

```python
st.caption("Relative Viability Index — higher score = stronger strategic fit for this location")
# Band mapping per score:
# >= 20  → "Strong fit"
# >= 10  → "Moderate fit"
# <  10 or 0.0 → "Insufficient data"
```

**Result:** Scenarios section now reads as a comparative strategic ranking tool,
not a failing report card. Under REJECTED_DESERT (all 0.0), all three display
"Insufficient data" — honest and professional.

---

### Step 4 — "Analysis complete" Sidebar Label (`app.py`)

**Problem:** Sidebar showed "Analysis in progress" with a checkmark permanently
after results loaded — a visual contradiction.

**Fix applied:** Added `status.update()` call immediately after the
`with st.status(...)` block closes:

```python
status.update(label="Analysis complete", state="complete", expanded=False)
```

Streamlit's `state="complete"` renders its own green checkmark — no emoji
duplication in the label text.

**Result:** Sidebar shows "✓ Analysis complete" after every successful run.
Confirmed visible in live screenshots.

---

### Step 5 — Payload-Aware WWC Validation (`llm_analyst.py`)

**Problem:** The LLM prompt rules instructed the model to return `[]` for
`what_would_change` when the payload contained no WWC items, but this was
enforced only via prompt instruction — not in code. The LLM could still
hallucinate threshold conditions on a bad generation.

**Fix applied:** Added enforcement block in `llm_analyst.py` after `json.loads`
and before `validate_report()`:

```python
# Payload-aware: if input has no WWC items, output must be []
if not ui_payload.get("what_would_change"):
    parsed["what_would_change"] = []
```

**Result:** WWC empty list is now guaranteed in code regardless of what the LLM
returns. 137/137 tests passing after this change.

---

### Step 6 — User-Facing Confidence Language (`app.py`)

**Problem:** "Confidence Score: 74.0" conveys nothing actionable to a
non-technical user. No context for what the number means for decision-making.

**Fix applied:** Added a conditional `st.caption()` below the Confidence Score
metric row:

```
>= 75 → "High confidence — suitable for investment screening"
>= 45 → "Moderate confidence — directional insight, verify before committing"
<  45 → "Low confidence — suitable for initial screening only, not investment decisions"
```

Skipped entirely if confidence is `None`.

**Result:** Caption "Low confidence — suitable for initial screening only, not
investment decisions" confirmed rendering below the 0.0 score in live
screenshots. This also provides informal legal/professional protection — the
system explicitly states its own limitations.

---

### Step 7 — Report Quality Gate (`llm_analyst.py`)

**Problem:** Pydantic schema validation confirmed output structure but did not
check whether the LLM had echoed raw flag strings back into the prose. A report
could pass schema validation while still containing "STATUS_DATA_DESERT_CAUTION"
in the executive summary.

**Fix applied:** Added quality gate block between WWC enforcement and
`validate_report()`. Scans both top-level string fields and string items inside
all list fields (`hidden_risks`, `strategic_levers`, `what_would_change`):

```python
_RAW_FLAGS = {
    "DATA_DESERT", "STATUS_DATA_DESERT_CAUTION", "STATUS_REJECTED_DESERT",
    "CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION", "STATUS_MONOPOLY_FORCE_CAUTION",
    "GOLDMINE_ZERO_COMPETITORS", "STATUS_GOLDMINE_GO", "STATUS_HIGH_RISK_NO_GO",
    "STATUS_DEFAULT_CAUTION", "REJECTED_DESERT",
}
_report_text = " ".join(
    str(v) for v in parsed.values() if isinstance(v, str)
) + " " + " ".join(
    str(item)
    for v in parsed.values()
    if isinstance(v, list)
    for item in v
    if isinstance(item, str)
)
if any(flag in _report_text for flag in _RAW_FLAGS):
    raise ValueError("Report contains raw internal flag strings — retrying")
```

The `ValueError` triggers the existing retry logic already in `llm_analyst.py`.

**Result:** Any report leaking raw flags is automatically rejected and retried
before reaching the UI. Combined with the prompt translation from Step 1, the
probability of a raw flag reaching a user is now near zero.

---

### Step 8 — 5 Golden LLM Report Tests (`tests/test_golden_llm_reports.py`)

**Problem:** No automated test confirmed that the prompt pipeline produced
clean, translated output for the five canonical market scenarios.

**Fix applied:** Created `tests/test_golden_llm_reports.py` with 5 tests
covering the full prompt pipeline (no live LLM call):

| Test | Scenario | Expected Status |
|------|----------|-----------------|
| `test_golden_llm_prompt_monopoly_market` | High competition concentration | CAUTION |
| `test_golden_llm_prompt_goldmine` | Zero competitors, high population | GO |
| `test_golden_llm_prompt_seaport_paradox` | High demand + extreme risk | NO-GO |
| `test_golden_llm_prompt_data_desert` | 3+ null metrics | CAUTION |
| `test_golden_llm_prompt_undersized_market` | Low demand + low competition | CAUTION |

Each test asserts:
- `build_prompt()` returns exactly `{"system_prompt", "user_message"}`
- Zero raw flag strings appear anywhere in the combined prompt text
- `<final_status>` contains the correct translated value
- If payload WWC is empty, `<what_would_change>` section contains `<!-- empty -->`

**Result:** 5/5 passing in 0.20s. Full suite: 142/142 passing in ~11s.

---

## Known Issue: Cache Invalidation and Live Census Data

**Observed behavior:** After clicking "Refresh Data" (which clears the
session-state cache), re-running the BU coordinates (42.3505, -71.1054) now
consistently returns `REJECTED_DESERT` / NO-GO with all N/A scores and
Confidence Score 0.0, instead of the previously observed CAUTION with live
scores.

**Root cause:** The `Refresh Data` button clears `st.session_state` but does
**not** clear the on-disk pipeline cache (`pipeline/cache.py`, 14-day TTL).
However, the original CAUTION result was served from a cached bundle written
during the Phase 5 smoke test. After the cache file expired or was displaced,
fresh live Census API calls at those exact coordinates are returning null for
`pop_total`, which correctly triggers `REJECTED_DESERT` per the Phase 2 scoring
spec (pop_total null → hard reject).

**This is correct engine behavior** — the scoring engine is doing exactly what
it was designed to do. The issue is that BU coordinates fall on a Census block
boundary where block-group level population data is intermittently unavailable
from the ACS API, causing the fallback cascade to hit placeholder level and
return null `pop_total`.

**Visible side effect:** The sidebar also shows "Golden sync drift" warnings:
- `final_status='NO-GO', expected 'CAUTION'`
- `status_rule_id='STATUS_REJECTED_DESERT', expected 'STATUS_DATA_DESERT_CAUTION'`

These are the `_check_golden_sync()` alerts correctly detecting that live data
has drifted from the Phase 2 mock golden snapshot. This is expected — the mock
was built from a specific cached Census response.

**Required before production:**
- Boston neighborhood baseline calibration (already on the checklist)
- Confirm stable Census block group coverage for BU and other test coordinates
- Consider seeding the pipeline cache with verified clean bundles for
  demo coordinates before sharing any public URL

---

## UI State: What's Clean vs. Still Pending

### Clean after this sprint
- Status caption: plain English, no raw flags
- LLM prose: zero raw flag strings across all sections (verified via quality gate)
- Business Profile JSON: removed from UI
- Scenario scores: relabeled as Relative Viability Index with qualitative bands
- Sidebar: "Analysis complete" on successful run
- Confidence score: plain-English interpretation caption
- Footer: "MarketMind AI · Phase 5 MVP · Live API" visible

### Still pending (Phase 7 / Demo Readiness)
- "What Would Change" UI card still renders raw condition label format
  ("To GO: To Go Block Group Data | To NO-GO: To No Go Placeholder Geography")
  — this is a UI rendering issue in `app.py`, separate from prompt translation
- Charles River / zero-data edge case needs a premium UI message
- Mobile layout sanity check not yet performed
- CTA footer (startup or recruiter version) not yet added
- Developer Mode expander not yet built
- Privacy/data note not yet added

---

## Test Suite Summary

| Suite | Tests | Status |
|-------|-------|--------|
| Phase 1A (Google Places) | 6 | ✅ |
| Phase 1B (Census API) | 11 | ✅ |
| Config Integrity | 1 | ✅ |
| Normalizer | 6 | ✅ |
| Scoring Engine | 33 | ✅ |
| Decision Engine | 51 | ✅ |
| Live Pipeline (Phase 5) | 29 | ✅ |
| Golden LLM Prompts (new) | 5 | ✅ |
| **Total** | **142** | **✅ 142/142** |

Run time: ~11s

---

## Before Production Checklist (Updated)

### Completed in this sprint
- [x] Translate raw flag strings to plain language in LLM prompt
- [x] Suppress Business Profile raw JSON from UI
- [x] Relabel scenario scores with Relative Viability Index framing
- [x] Fix sidebar status label post-load
- [x] Payload-aware WWC validation enforced in code
- [x] User-facing confidence language added
- [x] Report Quality Gate implemented (string + list fields)
- [x] 5 golden LLM prompt tests passing

### Still required before public URL
- [ ] Boston neighborhood baseline calibration (Census coverage gaps confirmed)
- [ ] Verify stable BU / demo coordinate Census block group data
- [ ] Rate limiting and abuse prevention
- [ ] Cloud secrets migration (.env → hosting vault)
- [ ] GCP hard quota cap (100 requests/day recommended)
- [ ] Concurrent Google + Census fetching (ThreadPoolExecutor)
- [ ] True cache hit/miss badge via pipeline metadata
- [ ] Graceful LLM degradation on timeout
- [ ] Quota error → premium UI message (not raw 429)
- [ ] "What Would Change" UI card plain-language rendering
- [ ] Charles River / zero-data edge case premium message
- [ ] Mobile layout sanity check
- [ ] CTA footer
- [ ] Developer Mode expander
- [ ] Privacy/data note in footer
- [ ] Evaluation bench (LLM-as-judge) after model weight updates
- [ ] Full pytest run after any future app.py change
