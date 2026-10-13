# To do

Steps we're working through one at a time. Each gets discussed before it's built.

## In progress
- [ ] **Load Florida PUMS** (2024 1-year housing file) — `ptm/load.py`

## Done
- [x] **Florida parcel rolls, all 67 counties** (2026-10-13; 29 final, 38 preliminary) — `scripts/fl_parcels.py`; checks in `data/processed/fl_nal_2026/_checks.csv`. 9.86M residential parcels, 5.21M homesteads, 717 MB processed. Rerun later for final rolls.
  - [ ] Look into Escambia: 41 parcels with missing just value.

## Next
- [ ] **Link PUMS and parcel data** (after aging PUMS to 2026). No record-level join is possible, so link by groups:
  1. Map parcels to PUMAs (`CENSUS_BK` → tract → PUMA).
  2. Age PUMS to 2026.
  3. Build cells: PUMA × value band × homestead/owner (maybe building type).
  4. Impute from parcels to households within cells: Save Our Homes gap (sharpen with `MV` vs last sale year), exemptions, land share, top-tail values (Method B).
  5. Calibrate PUMS totals by PUMA to the roll (homestead counts, value, taxable value).
  - Check: Florida "just value" vs market value (believed ~15% below market for cost of sale — confirm).
  - Result is a 2026 baseline *dataset*; still needs millage calibration, tax rules as code, renters, projection, metrics.
- [ ] **Two-part structure:** households (PUMS + roll) for distribution; all parcels (roll directly) for revenue, since second homes, investor-owned rentals and vacant land aren't PUMS households (and Amendment 3's 5% cap mainly hits them). Same tax-rule code for both.
- [ ] **Top-coded home values** — Pareto tail, Method B: fit to the Florida DOR parcel tax roll. Method A (fit from PUMS just below the cut-off) is the fallback for states without usable parcel data. Details in `CHALLENGES.md`.
- [ ] **Age to 2026.** Two target dates:
  - **values → Jan 1, 2026** (Florida assessment date; matches the 2026 roll);
  - **incomes and rents → calendar-year 2026 average** (income during the year the 2026 bill is paid; PUMS income is effectively calendar-2024 income).
  - [x] **Home values, by county × type × tier** — `add_aged_values` in `ptm/aging.py`; inputs from `scripts/value_factors.py`:
    - Step A, market growth 2024 avg → Dec 2025 (Zillow ZHVI by county; single-family/condo × bottom/mid/top tier; mobile homes = bottom tier), **level-corrected with the roll's own sales** (sale ÷ appraisal ratio, Jan–Jun 2025 vs 2026) → `inputs/value_growth_fl_2026.csv`. Median owner market value $388k → $373k (single-family +0.8%, condo −12.3%).
    - Step B, market → just value: median just value / H2-2025 qualified sale price ≈ 0.83, by county × type × tier (fallbacks if < 30 sales) → `inputs/just_value_ratio_fl_2026.csv`.
    - Check vs roll: PUMS aged just value is ~4% below roll homestead medians statewide; still 10–24% below in South Florida. Resolve in linking/calibration (see CHALLENGES).
    - [x] Cross-check Zillow against FHFA metro index → Zillow overstated the decline; corrected with sales.
    - [ ] Upgrade Step A with 2024 sales from the 2025 roll (by request) or 2024 vs 2026 roll values.
  - [x] **New development** — `ptm/reweight.py`: targets from the roll (homesteads built 2024–25; multi-family units built 2024–25 × 0.9 occupancy), minus PUMS households already in 2024-built homes; donors = same tenure, `YRBLT` ≥ 2020, same PUMA (pooled to county if < 10 donors or multiplier > 4). Owners +122,612 (+2.0%), renters +121,935 (+4.4%); 4,742 records reweighted, median multiplier 1.31, max 3.78; replicate weights scaled too. Distributions barely move (free & clear 44.1% → 43.8%, moved in < 2 yrs 12.6% → 13.2%).
    - Single-family rentals (built-to-rent) left out — can't separate from second homes in the roll.
    - [ ] Repeat each projection year.
  - [x] **Incomes by type** — `ptm/aging.py`, factors from `scripts/aging_factors.py` → `inputs/aging_factors_2026.csv`. Wages/self-employment +9.8% (QCEW FL private avg weekly wage, Q1 2026 vs Q1 2024), Social Security/SSI +5.4% (COLAs), other +6.0% (CPI-U). Rerun the script when later 2026 QCEW quarters are published.
  - [x] **Rents** — `add_aged_rent` in `ptm/aging.py`: contract rent by CPI rent area (Miami +6.6%, Tampa +6.3%, rest of FL via South region +5.0%); utilities part of gross rent by CPI-U. PUMA → main county → area in `ptm/geo.py`. Revisit with pass-through.
  - [x] **`TAXAMT`, provisional** — `add_aged_taxamt`: × Save Our Homes caps (2025 2.9%, 2026 2.7%) = +5.7%, rates held fixed; original `TAXAMT` kept as anchor. (Statewide levy growth was rejected: it includes new homesteads at full value, so it overstates incumbents' growth.)
  - [x] **`TAXAMT`, rule-based** — `add_aged_taxamt_rules` in `ptm/aging.py`, rules in `ptm/florida.py`, history from `scripts/fl_soh_history.py` → `inputs/fl_soh_history.csv`. Purchase year from `MV`; 2024 assessed/just ratio from Save Our Homes caps vs Florida price index since purchase; roll assessed value forward (min(prior × cap, just value)); school/non-school taxable after homestead exemption (indexed second exemption); rates fixed, school share 0.37. Result: median owner tax +6.4%, total +5.4%, 8.9% of owners see a decrease (recent buyers, where values fell). Supersedes the provisional caps-only version.
    - Check: modelled 2026 assessed/just median 0.63 vs roll homesteads 0.66; but county correlation only 0.40 (statewide price index; ignores portability). Refine with county indexes / parcel imputation at linking.
    - [ ] Replace `SCHOOL_SHARE` (0.37, rough) with county millage at calibration.
    - [ ] Unit tests for `ptm/florida.py` (add pytest).
  - **Household count:** handled by calibration to the roll's 2026 homestead count.
- [ ] **Request 2024 final NAL roll** from DOR (PTOTechnology@floridarevenue.com) — draft ready on request; you send it.
- [ ] **Florida current-law rules** — Save Our Homes, homestead exemption, 10% non-homestead cap
- [ ] **Calibration** — match modelled tax to reported `TAXAMT` and published levy totals
- [ ] **Metrics** — distribution tables by income decile etc., Suits index, replicate-weight SEs
- [ ] **Current-law projection** — 2026 → 2036
- [ ] **Amendment 3** (Florida, Nov 3 2026 ballot) — first policy
- [ ] **Ohio** — HB 920 reduction factors; Ramaswamy rollback-then-cap (rollback year as a setting)
- [ ] **Texas**

## Deferred: pass-through to renters
For now the model looks at nominal property tax only. Later we need to decide how landlords' tax reaches renters. Options discussed:
- one pass-through share for everything;
- different shares for increases vs decreases;
- gradual pass-through over several years (fits the year-by-year design);
- land vs building split (the tax on land mostly stays with landowners; needs outside land-value data).

Also to decide:
- Report a separate **landlord** line in winners/losers totals for the tax that isn't passed on.
- How to treat `TEN` 4 (occupied without paying rent): no burden, or a burden based on similar rented homes.

## Open questions from loading
- **Income top-coding.** `flag_topcode_hincp` is meaningless: PUMS top-codes income components (wages, etc.) per person, not household income, so there's no tie at the max. Decide whether to drop it or detect top-coding properly from the person file.

## Future option: link voter file
Florida's voter file (Division of Elections, on request; check use terms and exempt voters) could be joined to parcels to study the political economy of property tax (e.g. turnout of Save Our Homes beneficiaries, Amendment 3 gains by party, homeowner vs renter turnout). Approach: match voters to parcels on **property address** (covers renters), using owner name only during matching; keep only derived parcel-level attributes; drop names and birth dates; report in aggregate only. Waiting on which research question to prioritize.

## Settings to keep in mind
- Caps can limit **assessed value** (default) or the **tax bill**.
- **Rollback year** (2019 / 2020 / 2021) is a separate setting from the 2026 base year.
