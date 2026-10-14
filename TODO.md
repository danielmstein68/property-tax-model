# To do

Steps we're working through one at a time. Each gets discussed before it's built.

## In progress
- [ ] **Load Florida PUMS** (2024 1-year housing file) — `ptm/load.py`

## Done
- [x] **Florida parcel rolls, all 67 counties** (2026-10-13; 29 final, 38 preliminary) — `scripts/fl_parcels.py`; checks in `data/processed/fl_nal_2026/_checks.csv`. 9.86M residential parcels, 5.21M homesteads, 717 MB processed. Rerun later for final rolls.
  - [ ] Look into Escambia: 41 parcels with missing just value.

- [x] **2026 baseline file** — `ptm/baseline.py`, `scripts/build_baseline.py` → `data/processed/baseline_fl_2026.parquet` (+ `.json` with build metadata, + new-development report). 87,327 records, 9,386,218 weighted households. Aged and reweighted; not yet linked or calibrated.

## Where we left off (2026-10-13)
Finishing the baseline = linking to parcels + calibration. Agreed order; decisions pending marked **?**:
1. [x] **Homestead status** — `assign_homestead` in `ptm/link.py`, in the baseline build. Targets: roll homesteads by PUMA × home type (multi-family 003/008 and co-op 005 homesteads count as condo). Households chosen by score = random + **implied-rate signal** (reported tax too high for a homestead, vs owners in the same PUMA with similar time in the home) + 0.25 × demographic signals (non-citizen, snowbird profile, moved < 1 yr). Result: 5.15M homesteads, 903k non-claimers; non-claimers pay 2.06× the tax per dollar of value (roll implies ~2×); demographic-only or random gave 1.00×. `non_claim_reason`: 214k likely ineligible, 689k possibly eligible.
   - Why the implied rate: demographic signals alone shifted *who* was picked but not their tax; reported tax is the direct evidence. Comparing with similar-tenure neighbours fixed long-time owners being over-picked (from 27% to 21% for 30+ years) because the Save Our Homes gap estimate is too deep for them.
2. [x] **Mobile homes on rented lots** — `assign_mobile_home_lots` in `ptm/link.py`, in the baseline build. Per PUMA: PUMS mobile-home owners − roll homestead mobile-home parcels (230k) = rented lot (294,747 assigned); priority lot < 1 acre, $0 tax, high `MHP` (includes site rent), low value. Flag `mh_rented_lot`: no real-estate tax, no homestead; their burden comes via lot rent (pass-through).
3. [x] **Assessment gaps** — `assign_assessment_gaps` in `ptm/gaps.py`, in the baseline build after value calibration; tests in `tests/test_gaps.py`. Each owner gets school and non-school assessed/just ratios from a roll donor in the same county group × home type × value third × homestead status. Homesteads are ordered by a 50/50 blend of the move-in-year estimate and the gap implied by reported tax; non-claimers by move-in. Results: area pattern matches the roll (correlation 0.41 → 1.00); move-in pattern kept (recent 1.00 → 30+ yrs 0.35); fit to reported tax improved (spread 0.80 → 0.57). Tax-only ordering fit better (0.32) but gave recent buyers a 0.71 ratio (should be 1.0) — rejected as overfitting. New columns `av_ratio_sd`, `av_ratio_nsd`, `av_sd_2026`, `av_nsd_2026`.
4. [x] **Top-coded values** — `ptm/topcode.py` (`impute_topcoded_values`), tests in `tests/test_topcode.py`. Draws from the roll's real homesteads above the statewide cut-off ($3.09M, 2024 market), by region (11 counties + rest), matched by reported tax with noise. All 706 records replaced (min $3.09M, weighted mean $5.94M, max $263M). `valp_2024` holds the corrected value (VALP untouched); tax aging uses it.
   - [x] In the baseline build (step 5, after `add_aged_values`, before `add_aged_taxamt_rules`); report saved as `baseline_fl_2026_topcode_report.csv`.
   - [ ] Top-coded tax ($42,500): impute at piece 7 from taxable value × county rates.
5. [x] **$0-tax owners and special exemptions** — `assign_exemptions` in `ptm/exemptions.py`, in the baseline build after assessment gaps; codes in `inputs/fl_exemption_codes.csv` (from the DOR NAL user guide). Roll: 3.9% of homesteads have $0 taxable, 77% from the disabled veterans' total exemption; PUMS homesteads report $0 at 4.3% — most zeros are real. Assigned to homesteads, matching roll counts by county group: veterans' total exemption (157,529; chosen mainly by reported $0 + veteran/widowed-65+ signals; 92% of holders report $0), totally disabled (14,462), long-term low-income senior (24,099), low-income senior (249,514; income test excludes Social Security/SSI as an AGI proxy, 2026 limit $38,686), veterans' discount (22,362). New columns `ex_*`, `taxable_sd_2026`, `taxable_nsd_2026`, `zero_tax_class`: of 223,469 $0 owners, 150,400 total exemption, 4,100 cheap home, 69,000 misreported (get a modelled tax at piece 7).
   - Small exemptions ($500 widow/blind/disabled, $5,000 disabled ex-service) not assigned yet.
6. [x] **Calibrate values** — `calibrate_values` in `ptm/calibrate.py`, in the baseline build after homestead status. Decided: match percentiles (quantile mapping), not reweighting. Homesteads mapped onto roll homestead just values by county group (41 groups, `county_groups` in `ptm/geo.py`) × home type; top-coded households included (their draws set the order, the roll sets the level); non-claimers get the homesteads' ratio at the same value position; thin cells (33 of 123) use a statewide ratio per type. Result: medians match the roll in all 90 mapped cells; homestead total $2.327T vs roll $2.354T. Miami-Dade single-family median $437k → $529k; Duval $308k → $290k. New columns `valp_jv_cal`, `valp_market_cal`, `value_cal_factor`.
   - Tax aging (`taxamt_aged`) still uses pre-calibration values; pieces 3 and 7 recompute taxable value from calibrated values.
7. **Tax rates** — 2026 county millage (DOR); replace school share 0.37; calibrate tax to `TAXAMT` and levies.

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
  - **Take-up setting** (default off): "possibly eligible" non-claimers start claiming with probability rising in the benefit (bigger exemptions → more filers → bigger revenue loss). Show static and with-take-up results.
  - **Snowbird residency switch** (default off): some likely-ineligible snowbirds move legal residency to Florida.
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
