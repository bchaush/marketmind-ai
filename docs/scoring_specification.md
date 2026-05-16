# MarketMind AI — Scoring Specification

**Document ID:** `phase2_scoring_spec_v0.1`  
**Status:** Draft constitution for Phase 2 (Scoring Engine)  
**Scope:** Mathematical and rule definitions only. Phase 2 code must implement this document verbatim. No external APIs in Phase 2. Inputs are Phase 1 unified bundles only (see §9).

---

## 1. Pillar Architecture

Phase 2 produces **six** scores on the closed interval **[0, 100]** (integers after rounding unless otherwise noted). Each score is computed only from the Phase 1 bundle fields listed below.

Notation:

- **↑ better** — a higher raw value should push the *user-facing* interpretation in a favorable direction for a prospective operator (after any direction flip inside formulas).
- **↑ worse** — a higher raw value is unfavorable to the prospective operator.

| Pillar | Range | Primary Phase 1 inputs | What it tells the user | Score direction (higher pillar value =) |
|--------|-------|-------------------------|-------------------------|-------------------------------------------|
| **Demand Score** | 0–100 | `demographic_data.pop_total`, `demographic_data.age_22_34_count`, `demographic_data.college_student_population_pct` | How strong local demand is for the chosen business type from population structure. | **Better** (more demand signal → higher score). |
| **Competition Pressure Score** | 0–100 | `competitor_data.summary.total_count`, `competitor_data.summary.avg_rating`, `competitor_data.summary.top_3_review_share_pct` | How crowded and how strong nearby competitors are within the search radius. | **Worse** (more pressure → higher score). |
| **Market Gap Score** | 0–100 | Same as Demand inputs **plus** `total_count` (used as **supply** proxy; higher count reduces gap). Gap is a **constructed** index: demand-side normalized signals minus competition-supply pressure (see §5–§6). | Whether local demand appears under-served relative to visible competitor supply. | **Better** (larger gap → higher score). |
| **Risk Score** | 0–100 | `demographic_data.rent_to_income_ratio`, `demographic_data.median_household_income`, `competitor_data.summary.top_3_review_share_pct` (concentration risk), `competitor_data.summary.avg_rating` (incumbent strength) | Financial and market-structure risk for a new entrant. | **Worse** (more risk → higher score). |
| **Opportunity Score** | 0–100 | Combines **normalized** Demand, inverted Competition Pressure, and Market Gap (see §5). No extra raw fields beyond those already named in Demand, Gap, and Competition pillars. | Holistic “should I dig deeper here?” headline combining demand, gap, and ability to win share. | **Better** (more opportunity → higher score). |
| **Confidence Score** | 0–100 | `demographic_data.geography_level`, `demographic_data.confidence_score` (Phase 1 census confidence), `demographic_data.fallback_used`, count and severity of **nulls** in scored metrics, `null_adjustments[]` length, and edge-case flags (§7). | How much to trust the five substantive scores given data completeness and geography fidelity. | **Better** (more trust in the numbers → higher score). |

**Explicit raw-metric directions** (used inside normalization, before any flip for pillar direction):

| Raw field | Direction for operator |
|-----------|-------------------------|
| `pop_total` | Higher → better (more people). |
| `age_22_34_count` | Higher → better (core coffee-shop cohort in this strategy). |
| `college_student_population_pct` | Higher → better (aligns with campus-adjacent coffee strategy). |
| `median_household_income` | Higher → better (more spending power; also reduces “affordability stress” when combined with rent). |
| `rent_to_income_ratio` | Higher → worse (housing cost burden / fragility). |
| `total_count` | Higher → worse (more competitors). |
| `avg_rating` | Higher → worse (stronger incumbents). |
| `top_3_review_share_pct` | Higher → worse (reviews concentrated in a few players → harder to win attention). |

---

## 2. Normalization Rules

### 2.1 Global constraints

- All pillar outputs are **0–100**. No internal 0–10 scale.
- Normalized metric values used in weighted sums are denoted **N(metric) ∈ [0, 100]**.
- **Linear (min–max)** is used when the raw distribution is roughly **uniform** across typical urban search radii and differences at the high end are still actionable (e.g. competitor counts in a 1-mile window).
- **Logistic (sigmoid) curve** is used when **diminishing returns** apply: the first few hundred residents or income dollars move the business case more than marginal increments at very high values.

### 2.2 Why diminishing returns (Boston context)

In Greater Boston block groups, moving from **~0 to ~500** residents often captures the difference between a non-viable pocket and a viable walk-up catchment; moving from **10,000 to 10,500** rarely changes the coffee-shop thesis because operations are already saturated by overlapping trade areas and multi-BG cannibalization. The same logic applies to youth cohort counts near institutions like Boston University: the first **~100** 22–34-year-olds in a BG materially changes queue and repeat-visit potential; very large counts still matter but at a declining marginal rate.

### 2.3 Sigmoid anchor convention

For each sigmoid-normalized metric **M** (higher raw = better unless noted), define **N(M)** using a **logistic** in **log₁₀(1 + raw)** space for counts, and in **raw** space for bounded ratios/percentages.

Let **x = g(raw)** where **g** is `log10(1 + max(raw, 0))` for non-negative counts, and `raw` for rates already in [0, 1] or [0, 100] as documented.

Use the **logistic**:

\[
N(M) = \frac{100}{1 + \exp\left(-k \cdot (x - x_{50})\right)}
\]

Choose **k** and **x₅₀** so that the following **anchor equalities hold** (solved numerically in implementation; values below are the **constitution** the code must match):

#### A) `pop_total` (Coffee Shop, higher better)

Saturation anchors (raw population in block group):

| Target N(pop_total) | Raw `pop_total` | Justification (Boston) |
|----------------------|-----------------|-------------------------|
| **10** | **200** | Below ~200, many Boston BGs are institutional, park, or thinly populated relative to street retail; foot traffic is often too thin for a general coffee shop without a captive facility. |
| **50** | **1,000** | ~1k aligns with a **mixed residential / student-adjacent** BG typical of inner Boston and near-university corridors—median-ish viability for walk-in retail. |
| **90** | **3,500** | ~3.5k matches **high-density residential** BGs common in Fenway, Allston, and downtown-adjacent neighborhoods where multiple cafés can still coexist. |

**Calibration procedure (law for implementers):**  
Set **x = log₁₀(1 + pop_total)**. Solve for **(k, x₅₀)** so that **N(200)=10**, **N(1000)=50**, **N(3500)=90** under the logistic above. No other ad hoc tuning is permitted.

#### B) `age_22_34_count` (Coffee Shop, higher better)

| Target N | Raw count | Justification (Boston) |
|----------|-----------|-------------------------|
| **10** | **30** | Very small youth cohort in BG → limited weekday lunch and study-hour velocity. |
| **50** | **120** | Typical for **student-adjacent** but not dominant BGs. |
| **90** | **400** | Strong youth/student-heavy BG consistent with **BU / Fenway / Cambridge** pockets. |

Use **x = log₁₀(1 + age_22_34_count)** and the same logistic form; solve **(k, x₅₀)** from the three anchors.

#### C) `college_student_population_pct` (Coffee Shop, higher better)

Treat raw **p** as a fraction in **[0, 1]** (if Phase 1 ever emits 0–100, divide by 100 first).

| Target N | Raw **p** | Justification |
|----------|-----------|-----------------|
| **10** | **0.05** | Low student share; household-driven demand dominates. |
| **50** | **0.20** | Meaningful student mix typical near urban campuses. |
| **90** | **0.45** | Very high student share; strong fit for campus-adjacent coffee strategy. |

Use **x = p** (linear domain is acceptable) with the logistic; solve **(k, x₅₀)** from anchors.

#### D) `median_household_income` (higher better)

Income exhibits diminishing returns; use **x = log₁₀(max(income, 1))** (USD).

| Target N | Raw income (USD) | Justification (Boston metro cost baseline) |
|----------|------------------|---------------------------------------------|
| **10** | **35,000** | Severe spending-power constraint vs. Boston living costs. |
| **50** | **75,000** | Working / young-professional band common in many Boston BGs. |
| **90** | **130,000** | High purchasing-power BGs (not exhaustive “rich” tail). |

Logistic on **x** with anchors as above.

#### E) `rent_to_income_ratio` (higher worse — invert after N)

First map raw ratio **r** (dimensionless; if Phase 1 stores percent, divide by 100) with **higher = more risk**:

| Target N_risk_component | Raw **r** | Justification |
|-------------------------|-----------|----------------|
| **10** (low risk contribution) | **0.15** | Moderate housing burden band. |
| **50** | **0.30** | High stress threshold commonly cited in housing literature. |
| **90** | **0.45** | Severe burden; operator risk from customer fragility. |

Use logistic where **higher r → higher internal S**. The pillar **Risk Score** uses **higher = worse**, so this internal **S** feeds Risk **without** direction flip.

### 2.4 Linear (min–max) metrics

#### F) `total_count` (competition count, higher worse)

For **Competition Pressure**, use min–max on **[0, C_max]** with **C_max = 40** for **radius_miles ≤ 1.0** (scales with radius in implementation table v0.1: for 1 mi use 40; for 0.5 mi use 25; for 2 mi use 55 — **Coffee Shop v0.1** locks **1.0 mi → C_max = 40**).

\[
S_{count} = \min(\max(\text{total\_count}, 0), C_{max})
\]
\[
N_{pressure\_from\_count} = 100 \cdot \frac{S_{count}}{C_{max}}
\]

**Rationale:** Competitor counts within 1 mi in Boston rarely exceed ~40 for coffee taxonomy after filtering; the distribution is **broad and roughly linear** in perceived crowding per added competitor up to the cap.

#### G) `avg_rating` (higher worse)

Clamp to **[3.0, 5.0]** (below 3 treated as 3 for normalization stability; above 5 treated as 5).

\[
N_{pressure\_from\_rating} = 100 \cdot \frac{\text{avg\_rating} - 3.0}{5.0 - 3.0}
\]

#### H) `top_3_review_share_pct` (higher worse)

Interpret as **0–100** percentage.

\[
N_{pressure\_from\_concentration} = \min(\max(\text{top\_3\_review\_share\_pct}, 0), 100)
\]

(It is already on a 0–100 scale; linear.)

### 2.5 Inversions (explicit)

When a **higher raw** metric is **better** for the operator but feeds a **worse-is-higher** pillar (e.g. Risk uses income as **relief**), define:

\[
N_{\text{relief}} = 100 - N(\text{median\_household\_income})
\]

(with **N(income)** from §2.3.D before inversion).

When feeding **Opportunity** from **Competition Pressure** components, use:

\[
N_{\text{ease}} = 100 - N_{\text{pressure\_component}}
\]

per component, **after** each component’s own normalization.

---

## 3. Null Handling and Weight Redistribution

### 3.1 Absolute rules

1. **Nulls are never coerced to zero, mean, median, or model imputations.**
2. If metric **M** is **null** for a weighted sum inside a pillar:
   - **Remove** weight **w_M** from that pillar’s active weight pool.
   - **Redistribute** removed weight **proportionally** across remaining **available** metrics in **that same pillar** that are non-null.
3. Apply a **confidence penalty** **P_null** per null metric (see §3.3).
4. Append a human-readable string to **`null_adjustments[]`** describing the pillar, metric, and redistribution targets.

### 3.2 Proportional redistribution (formula)

Let the pillar’s baseline weights be **w_i** for metrics **i ∈ S**. Let **A ⊆ S** be indices where **raw_i is not null** and the metric participates in that pillar. For each null **j ∉ A**, define removed weight **Δ = w_j**.

Redistributed weight to an available metric **i ∈ A**:

\[
w_i' = w_i + \Delta \cdot \frac{w_i}{\sum_{k \in A} w_k}
\]

Repeat for each null metric sequentially in **ascending alphabetical order by metric name** (deterministic tie-break). After processing all nulls in that pillar, renormalize so that **∑_{i∈A} w_i' = 1.0** within floating tolerance **1e-9**.

### 3.3 Confidence penalty schedule

For **each** null metric encountered in **any** of the five substantive pillars (Demand, Competition, Market Gap, Risk, Opportunity), apply:

- **P_null = 4** points deducted from **Confidence Score** (floor at **§4** or **§7** hard floors if triggered).

Penalties **stack** additively across null metrics (multiple pillars can reference the same null; **penalize once per distinct metric name per bundle execution**, not once per pillar reference).

### 3.4 `null_adjustments[]` format

Each entry is a single string, canonical pattern:

`<metric> missing; weight redistributed across <comma-separated list>`

Example:

`median_household_income missing; weight redistributed across pop_total and age_22_34_count`

If a null metric is the **only** metric left in a pillar after others are null, that pillar cannot be computed per §7 (Desert / reject rules) or must use **pillar-specific fallback** documented in §7; **do not invent weights**.

### 3.5 Phase 2 output requirement

Top-level JSON must include:

`"null_adjustments": [ ... ]`

---

## 4. Anchor Metrics

### 4.1 Definition (Coffee Shop)

**Anchor metrics** for the Coffee Shop strategy:

1. `demographic_data.pop_total`  
2. `demographic_data.age_22_34_count`

### 4.2 Hard Confidence Warning (not a hard reject)

**Trigger:** Either anchor is **null** **and** Phase 1 indicates tract-level geography failed to restore anchors — operationalized as:

- `demographic_data.geography_level` is **`placeholder`** **OR**  
- `demographic_data.fallback_used` contains **`placeholder_used`** **OR** **`geocoder_insufficient_fips`**

**Behavior:**

- Emit **`hard_confidence_warning: true`** in Phase 2 output.
- Still compute all scores **unless** a **Desert hard reject** (§7) applies.
- Apply **Confidence Score floor** **F_anchor = 35** after all other confidence adjustments (penalties cannot reduce Confidence below **35** when this trigger fires; other floors in §7 take **precedence** if higher).

---

## 5. Score Direction and Weight Tables (Coffee Shop)

**Rule:** Within each pillar subsection, baseline weights **sum to 1.0**. Weights apply to **N(·)** after normalization and direction corrections per §2.

### 5.1 Demand Score

```json
{
  "demand_score": {
    "pop_total": 0.40,
    "age_22_34_count": 0.35,
    "college_student_population_pct": 0.25
  }
}
```

**Justification:** Population sets the **ceiling** on catchment (40%). Youth 22–34 is the **primary conversion cohort** for urban coffee (35%). Student share is a **strategy amplifier** near campuses but noisier / sparser in ACS (25%).

### 5.2 Competition Pressure Score

```json
{
  "competition_pressure_score": {
    "total_count": 0.45,
    "avg_rating": 0.35,
    "top_3_review_share_pct": 0.20
  }
}
```

**Justification:** Competitor **quantity** is the dominant crowding signal (45%). **Quality** (avg rating) captures how hard it is to win on product (35%). **Concentration** of reviews in top 3 captures oligopoly-style attention markets (20%).

### 5.3 Market Gap Score

Define **demand_proxy** and **supply_proxy**:

- **demand_proxy** = same weights and metrics as **Demand Score** (§5.1), including null redistribution rules.
- **supply_proxy** = **only** `total_count`, normalized as **N_supply = N_pressure_from_count** from §2.4.F (higher count → higher supply pressure).

```json
{
  "market_gap_score": {
    "demand_proxy": 0.70,
    "supply_proxy": 0.30
  }
}
```

**Construction:**

\[
\text{MarketGap} = \min\left(100,\ \max\left(0,\ 1.25 \cdot (\text{DemandScore}_{internal} - 0.65 \cdot N_{supply})\right)\right)
\]

Where **DemandScore_internal** is the weighted sum of demand metrics **before** the final Demand pillar rounding, on **[0,100]**. Constants **1.25** and **0.65** are **v0.1 law** (tune only via spec revision).

**Justification:** Gap is mostly “**people vs shops**” (70% demand proxy) but must penalize **dense competitor fields** (30% supply).

### 5.4 Risk Score

```json
{
  "risk_score": {
    "rent_to_income_ratio": 0.40,
    "median_household_income": 0.30,
    "top_3_review_share_pct": 0.15,
    "avg_rating": 0.15
  }
}
```

**Justification:** Rent burden is primary **customer financial fragility** signal (40%). Income is spending-power cushion (30%, inverted per §2.5). Concentration + incumbent strength capture **competitive risk** (30% combined).

### 5.5 Opportunity Score

**No independent raw weights** beyond composed pillars:

\[
\text{Opportunity} = \min\left(100,\ \max\left(0,\ 0.45\cdot \text{Demand} + 0.35\cdot \text{MarketGap} + 0.20\cdot (100 - \text{CompetitionPressure})\right)\right)
\]

**Justification:** Opportunity is primarily **demand** (45%), reinforced by **structural gap** (35%), tempered by **ease vs incumbents** (20% from inverted competition).

### 5.6 Confidence Score

Baseline starts from Phase 1 census confidence, then penalties.

```json
{
  "confidence_score": {
    "phase1_census_confidence": 0.60,
    "geography_fidelity": 0.25,
    "completeness_of_scored_metrics": 0.15
  }
}
```

**Definitions:**

- **phase1_census_confidence** = `demographic_data.confidence_score` rescaled if needed: if Phase 1 emits **0–100**, use as **C_p1 ∈ [0,100]** directly; multiply weight in composition below.
- **geography_fidelity** scoring table (v0.1):
  - `block_group` → 100  
  - `tract` → 75  
  - `zcta` → 55  
  - `placeholder` → 25  
- **completeness_of_scored_metrics** = **100 × (1 - null_rate)** where **null_rate = (# null among the set {pop_total, age_22_34_count, college_student_population_pct, median_household_income, rent_to_income_ratio, avg_rating, total_count, top_3_review_share_pct}) / 8**).

**Composition:**

\[
\text{Confidence} = \min\left(100,\ \max\left(0,\ 0.60\cdot C_{p1} + 0.25\cdot G_{fid} + 0.15\cdot C_{complete} - \sum P_{null}\right)\right)
\]

Then apply **floors** from §4 and §7 if triggered.

---

## 6. Narrative Output Schema

For **each** of the six scores, Phase 2 must emit:

```json
{
  "score": <int 0-100>,
  "confidence": <int 0-100>,
  "drivers": [ "...", "...", "..." ],
  "narrative_tag": "<single plain-English sentence>"
}
```

**Rules:**

- **`drivers`**: **2–3** strings, ordered by **absolute marginal contribution** to that pillar after null redistribution (largest first). If a metric is null, a driver may state unavailability (e.g. “Student population unavailable”) **only if** that metric was in the pillar’s baseline table.
- **`narrative_tag`**: **Exactly one** sentence; **deterministic** from template slots filled by numeric driver strings; **no LLM** may invent alternative causality in Phase 2.

### 6.1 Narrative tag templates (v0.1 law)

Each pillar’s `narrative_tag` must be assembled by selecting the bracketed slot values from fixed band rules (same LOW/MODERATE/HIGH bands as §6.2) and substituting live values from the bundle and top driver labels. Brackets indicate substitution slots, not output text.

**Demand**

`Local demand is [LOW|MODERATE|HIGH], driven by [top driver] in this block group.`

**Competition Pressure**

`Competitive intensity is [LOW|MODERATE|HIGH], with [total_count] active competitors averaging a [avg_rating] rating.`

**Market Gap**

`The market shows a [NARROW|MODERATE|WIDE] gap between local demand and existing supply.`

**Risk**

`Risk is [LOW|MODERATE|HIGH], primarily driven by [top risk driver].`

**Opportunity**

`Overall opportunity is [LIMITED|MODERATE|STRONG], reflecting [demand band] demand and [gap band] market gap.`

**Confidence**

`Data confidence is [LOW|MODERATE|HIGH] based on [geography_level] resolution and [null count] missing metric(s).`

### 6.2 Band thresholds for template slots

- **Demand, Competition Pressure, Market Gap, Risk:** **0–39 → LOW / NARROW** (Market Gap uses **NARROW** in this band), **40–64 → MODERATE**, **65–100 → HIGH** (Market Gap uses **WIDE** in this band; use **MODERATE** for the middle band).
- **Opportunity:** **0–39 → LIMITED**, **40–64 → MODERATE**, **65–100 → STRONG**.
- **Confidence:** **0–44 → LOW**, **45–74 → MODERATE**, **75–100 → HIGH**.

For Opportunity template slots: **[demand band]** and **[gap band]** use the same LOW/MODERATE/HIGH wording as Demand and Market Gap pillar scores respectively (LOW/MODERATE/HIGH, with Market Gap mapped: NARROW→LOW wording “narrow”, MODERATE→“moderate”, WIDE→“wide” in prose — implementation must emit the words **“low”, “moderate”, “high”** for demand band, and **“narrow”, “moderate”, “wide”** for gap band to match Market Gap bands).

---

## 7. Edge Case Thresholds

| Case | Condition | Behavior |
|------|-----------|----------|
| **Desert (hard reject)** | `pop_total` is **null** **OR** `pop_total == 0` | **Do not emit pillar scores** (or emit all five substantive scores as **`null`** with reason code `DESERT_POP`); **Confidence** may still be computed for transparency. Implementation must **abort scoring** flag `scoring_status: "REJECTED_DESERT"`. |
| **Monopoly (Critical Risk flag)** | `top_3_review_share_pct > 60` | Set `flags: ["CRITICAL_RISK_MONOPOLY_REVIEW_CONCENTRATION"]`. Add **+15** to **Risk Score** **before** capping at 100 (spec revision required to change). |
| **Goldmine** | `total_count == 0` **and** `pop_total > 2500` | Set `flags: ["GOLDMINE_ZERO_COMPETITORS"]`. Set **Opportunity Score = 100** and `market_gap_score` **≥ 85** after composition (if conflict, **Opportunity wins** at 100, Gap capped at 100). |
| **Data Desert** | **≥ 3** null metrics among the **eight** listed in §5.6 | Set `flags: ["DATA_DESERT"]`; apply **Confidence floor** **F_data = 40** (does not stack with **F_anchor**; use **max(F_anchor, F_data)**). |

**Null never equals zero:** Desert uses explicit **`pop_total == 0`** OR **`pop_total is null`** only.

---

## 8. Worked Example (Illustrative — Demand Score Only)

**Locked BU bundle excerpt:**

- `total_count` = 15  
- `avg_rating` = 4.43  
- `top_3_review_share_pct` = 45.9  
- `pop_total` = 1542  
- `age_22_34_count` = 158  
- `median_household_income` = null  
- `college_student_population_pct` = null  
- `rent_to_income_ratio` = null  

### Step A — Baseline Demand weights

- `w_pop = 0.40`  
- `w_age = 0.35`  
- `w_student = 0.25`  

### Step B — Null detection

- `college_student_population_pct` is **null** → remove **0.25**; redistribute to **pop_total** and **age_22_34_count** proportionally:

\[
\text{Sum of remaining baseline} = 0.40 + 0.35 = 0.75
\]

\[
w_{pop}' = 0.40 + 0.25 \cdot \frac{0.40}{0.75} = 0.40 + 0.13333... = 0.53333...
\]
\[
w_{age}' = 0.35 + 0.25 \cdot \frac{0.35}{0.75} = 0.35 + 0.11666... = 0.46666...
\]

Renormalize to sum 1.0 (already sums to 1.0 after this construction).

### Step C — Illustrative normalized values (not calibrating full logistic here)

Suppose the implementation’s logistic yields:

- **N(pop_total) ≈ 48** (1542 between 1000 and 3500 anchors)  
- **N(age_22_34) ≈ 52** (158 between 120 and 400 anchors)  
- Student term **omitted**

### Step D — Weighted Demand (internal, illustrative)

\[
\text{Demand}_{internal} \approx 0.5333 \cdot 48 + 0.4667 \cdot 52 \approx 25.6 + 24.3 \approx 49.9 \rightarrow 50 \text{ (rounded)}
\]

### Step E — `null_adjustments[]` (Demand-related entries)

- `college_student_population_pct missing; weight redistributed across pop_total and age_22_34_count`

### Step F — Confidence penalty (illustrative count)

Distinct null metrics in full bundle for this example: **{median_household_income, college_student_population_pct, rent_to_income_ratio}** → **3 × P_null = 12** points from Confidence before floors (student counts once globally).

**This section does not lock final Opportunity, Risk, Gap, or Competition scores.**

---

## 9. Phase 2 Hard Rules

1. The scoring engine **never** calls **any** external HTTP/API/SDK data fetch.  
2. **Input** is **only** a validated Phase 1 unified bundle JSON (same schema as the Phase 1 gate).  
3. **Reference fixture path** for tests and golden traces: **`mock_data/mock_boston_data.json`**.  
4. All outputs must be **deterministic** and **explainable** from this spec, the input bundle, and **fixed random seeds** (none should be needed; **no randomness**).  
5. **No LLM** may compute, adjust, or narratively override numeric scores in Phase 2. LLMs consume Phase 2 output only in Phase 3.  
6. Any change to weights, anchors, floors, or formulas requires a **new spec version** (e.g. `v0.2`); code must reference the spec version string in its output metadata.

---

**End of document — `phase2_scoring_spec_v0.1`**
