# To do

Steps we're working through one at a time. Each gets discussed before it's built.

## Open items (cleaned up 2026-10-16)
**Accuracy**
- [ ] Top-coded tax ($42,500, ~1% of PUMS owners): impute from taxable value x local rates.
- [ ] 2026 rates: swap in DOR's 2026 TACD / Table 1 when posted; collect remaining county rates; more 2026 city rates (Tampa, Orlando, Clearwater, Naples, Tallahassee, Gainesville, remaining Broward cities).
- [ ] County checks: Putnam (homestead tax 12% above the roll), Escambia (8% below; 41 parcels missing just value), homesteads under $100k (9% below).
- [ ] Senior long-term exemption: sliders barely move results (PUMS `MV` tenure bands); check eligibility by tenure.
- [ ] Separate 10-mill caps for county-dependent districts and MSTUs (needs per-authority rates); special-district class (independent districts, water management districts).
- [ ] Fix `inputs/fl_exemption_codes.csv`: codes 31-34 are $5,000 (not $500).
- [ ] Replace `SCHOOL_SHARE` (0.37) in `ptm/aging.py` tax aging with county millage.
- [ ] Reprocess NAL rolls so the stored `own_out_of_state` flag is correct (code recomputes it).
- [ ] Income top-coding flag (`flag_topcode_hincp`) is meaningless; drop or detect from the person file.

**Projections**
- [ ] Inflation: average CBO, SS Trustees, Philadelphia Fed SPF; expose an inflation control.
- [ ] Regional/type variation in appreciation (condos, Southwest Florida).
- [ ] Check first projected years against REC taxable value forecasts.
- [ ] Faster Monte Carlo (batch paths); new development reweighting each projection year.

**Behavioural responses**
- [ ] Owners dropping the exemption when a policy shrinks it (only claiming is modelled).
- [ ] Second-home switching in city bases and history-mode rate responses.

**Amendment 3 and policy**
- [ ] Local options: counties/cities raising the exemption; shortening the newcomer wait from 2030.
- [ ] County map of revenue lost and rate increases.
- [ ] (optional) Compare county/city/special district impacts with REC's per-government tables (impact0710.pdf pages 5-18).
- [x] Tests for 2026-10-15/16 features: `tests/test_policy_features.py` (10 tests; suite 78).

**Bigger**
- [ ] Live engine so users can combine changes freely (replaces the pre-computed grid).
- [ ] Texas (next; research in `docs/research/texas_homestead_takeup.md`), then Ohio (HB 920; rollback-then-cap).
- [ ] Renters / pass-through (dropped 2026-10-15; see below).

**Needs Daniel**
- [ ] Request the 2024 final NAL roll from DOR (draft ready; Daniel sends).
- [ ] Check the 29 fiscally constrained counties against EDR's map (Property-Tax-FiscallyConstrainedCounties.pdf, slide 3).
- [ ] Check the strike-through in SB 4-F s. 200.065(5)(a) (per capita income adjustment struck?).

---
# History and notes

## In progress (historical)
- [x] **Load Florida PUMS** (2024 1-year housing file) — `ptm/load.py`

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
7. **Tax rates and calibrated tax** — in progress.
   - [x] **2025 district rates for all 67 counties** (2026 not published yet; decided: build on 2025, swap in 2026 when DOR posts it). `inputs/fl_district_rates_2025/<County>.csv` (+ `notes/` per county): 58 from DOR TACD tables, 9 from appraisers/tax collectors (Broward, Lee, Brevard, Baker, Hernando direct; Palm Beach from an archived 2025 table; Sarasota = 2026 composition × 2025 certified rates; Gadsden, Liberty built from components). School millage for all 67 from FLDOE 2025-26 budget summaries (`inputs/fl_school_millage_2025.csv`); TACD school figures match FLDOE in every county (Pasco's stale table corrected).
   - [x] **Tax districts and modelled tax** — `assign_districts` in `ptm/millage.py`, in the baseline build: each owner gets a real roll parcel's district within PUMA × homestead × value third, ordered by tax-implied rate; modelled tax = school taxable × school millage + non-school taxable × non-school millage. All owners covered. Owners' modelled 2026 tax (2025 rates) $25.4B. Modelled ÷ reported: median 0.91 (middle half 0.71–1.19); big counties mostly 0.9–1.1; low in Polk, Marion, Brevard, Hernando (0.72–0.77), likely flat non-ad valorem fees owners include in reported tax.
   - [x] **Official replacements (approved downloads):** Orange from the Property Appraiser's 2025 FINAL totals (31 of 81 reconstructed codes were wrong, by up to 3 mills); Broward and Lee from DOR's 2025 TACD spreadsheets (Broward letter-suffix special districts now included). DOR spreadsheets confirm Baker, Brevard, Hernando, Palm Beach, Sarasota totals; Gadsden components match DOR authority rates.
   - [x] **Homestead check vs official levies** — `scripts/check_homestead_county_tax.py`: county-government taxes paid by homesteads, model (2026 homestead non-school taxable × county 2025 millage) vs official (Table 1 levy × Table 2 homestead share), 66 counties (Duval skipped: consolidated government). Statewide **1.049**; Broward 1.04, Miami-Dade 1.03, Palm Beach 1.03, Orange 1.05, Pinellas 1.05 — consistent with 2026 taxable ≈ 2025 × (cap growth + new homesteads). Outliers: Collier 0.89, Pasco/Osceola/Lake ~1.11.
   - [x] **Decided (option A): baseline tax = modelled tax** (rules × official rates), validated against official levies — not scaled to PUMS reported tax. Reported − modelled differs by county in a regional pattern (South Florida report less, e.g. Miami-Dade −$707/owner; Polk, Brevard, Lee report more), uncorrelated with flat fees per parcel (corr −0.09) — so it's survey reporting, not model error. Reported tax is used only as evidence for imputation (homestead status, gaps, districts). Misreported zeros and top-coded tax bills therefore just take modelled tax.
   - [x] **Flat fees (non-ad valorem):** not property tax, kept out of the baseline; DOR 2025 NAV reports downloaded for later use (e.g. renters, total bill comparisons).
   - [x] **Rules engine for taxable value:** `engine_tax` in `ptm/millage.py` feeds the other chat's engine (`ptm/engine`, law spec `inputs/fl_law.yaml`): av by levy class + exemption flags → taxable by class → × millage by class. Matches the earlier simplified taxable values for 100% of households (school, county). New: city senior exemptions (`ex_senior_lowinc_city` 75k, `ex_senior_longterm_city` 13k, matched to roll codes 04/40). Owner tax 2026: school $9.98B, county $12.61B, municipal $2.86B, total $25.44B.
   - [x] **Millage by levy class** — `district_classes` in `ptm/millage.py`: school (FLDOE), municipal (Table 1 city rate; district's city from rate-file notes, else parcels' mailing city accepted only if the county remainder ≥ the county government's rate), county = rest, special = 0 for now. 37% of homesteads in city districts.
   - [ ] Special-district class: break out independent districts and water management districts (affects only senior exemptions, ~$20/yr).
   - [ ] Swap in 2026 rates when DOR posts the 2026 TACD tables.
   - [x] Rate model (`ptm/ratemodel.py`, 2026-10-14): rolled-back rate from official data (2025 test vs DOR: median error -0.10%, 92% within 3%; 2026 vs 14 official/reported: median 0.55%); behaviours scored on 22 final 2026 county rates — keep last year's rate (capped at 110% of rolled-back) best (median error 0%, county revenue +0.21%); 2026 school rates from official FLDOE RLE; `county_general_2026()` uses 24 collected adopted rates (`inputs/fl_county_general_2026.csv`, sourced) else keep-rate. Owner tax on 2026 rates: $25.30B vs $25.43B on 2025 rates (school -1.1%, county -0.1%).
   - [x] 2026 rates wired into the baseline build (`apply_2026_rates`, step 13): official 2026 school RLE; county general rates adopted where collected (33 final, 81% of owners) else keep-rate; cities/special districts and Duval (consolidated) at 2025. 2025-rate values kept as `*_2025rates`. Owner tax $25.30B.
   - [ ] Collect remaining 2026 adopted county rates (web-search limit hit this session) or use DOR 2026 Table 1 when posted; verify news-only entries.
   - Small gaps: Lee 325 (263 homesteads, likely new 2026 district); Lake 3 / Flagler 1 / Bay 1 codes with ~0 homesteads; Liberty code mapping inferred.

## Next
- [x] **Link PUMS and parcel data** (done: homestead status, gaps, districts, calibration — see "Where we left off"). No record-level join is possible, so link by groups:
  1. Map parcels to PUMAs (`CENSUS_BK` → tract → PUMA).
  2. Age PUMS to 2026.
  3. Build cells: PUMA × value band × homestead/owner (maybe building type).
  4. Impute from parcels to households within cells: Save Our Homes gap (sharpen with `MV` vs last sale year), exemptions, land share, top-tail values (Method B).
  5. Calibrate PUMS totals by PUMA to the roll (homestead counts, value, taxable value).
  - Check: Florida "just value" vs market value (believed ~15% below market for cost of sale — confirm).
  - Result is a 2026 baseline *dataset*; still needs millage calibration, tax rules as code, renters, projection, metrics.
- [x] **Two-part structure** (done as households + roll-based local bases and non-owner estimate): households (PUMS + roll) for distribution; all parcels (roll directly) for revenue, since second homes, investor-owned rentals and vacant land aren't PUMS households (and Amendment 3's 5% cap mainly hits them). Same tax-rule code for both.
- [x] **Age to 2026.** Two target dates:
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
- [x] **Florida current-law rules** — spec done: `inputs/fl_law.yaml` (24 rules, verbatim sources, confidence flags), readable page `docs/FL_LAW.md` (`scripts/law_page.py`), loader `ptm/law.py`. Review decisions 2026-10-14 recorded in the spec. Still to do:
  - [x] Rules engine reading the spec (assessment, exemptions in statutory order, taxable value by levy class) + unit tests.
  - [x] Exemptions engine (`ptm/engine/exemptions.py`) — 15 hand-worked tests.
  - [x] Roll test (`scripts/roll_test.py`): 9,854,810 residential parcels, **99.39% exact** on both school and county taxable value (school 99.51%, county 99.43%); **99.82%** excluding explained cases (exemptions outside the spec, $10 condo common elements, Gadsden's preliminary roll using the 2025 second-band amount). 17,343 parcels left to explain (standard homesteads 9.5k, county senior 3.7k, veterans' discount 2.0k, $5,000 ex-service 1.7k).
  - [x] Exemption assignment updates (2026-10-14, `ptm/exemptions.py`, `ptm/millage.py`): county codes only for county senior counts (city 04/40 separate, eligibility-based so cities without a county ordinance get candidates); county-group senior amounts; long-term senior statutory test (just value < $250k in first qualifying year, deflated; 25+ years); total disability excludes Brevard's $5,000 code-08 entries (roll: 3,608 homesteads, not 14,967) with $0 reporters and the $37,712 gross-income limit first; new $5,000 exemptions assigned (widow/blind/disabled 561k, disabled ex-service 161k). Owner tax $25.441B → $25.425B; official-levy check 1.048; modelled/reported median 0.904.
  - [ ] Fix `inputs/fl_exemption_codes.csv`: codes 31–34 are $5,000 (not $500, per ch. 2022-97 and the roll).
  - [x] Assessment rules (`ptm/engine/assess.py`) — Save Our Homes cap with recapture, reset on sale / first homestead year, improvements, non-homestead 10% cap (school at just value). 12 hand-worked tests. Reset-on-sale checked against 2025 sales in the roll (non-homesteads 99.8%; homesteads 74.7%, rest explained by portability). Full test needs the 2025 roll (requested).
  - [x] Year-step (`ptm/engine/step.py`): `step()` = assessment → exemptions → taxable → tax (rates plug in as `millage_<class>` columns), `carry_forward()` for the next year. 6 tests incl. tax by hand and a three-year path. ~3.5 s per million units per year.
  - [x] Step 4 — wire the engine into the baseline (done: `engine_tax` in `ptm/millage.py`) (coordinate with the rates chat: `ptm/baseline.py`, `ptm/millage.py`, `ptm/exemptions.py`, `ptm/aging.py`): household taxable values from the engine (four levy classes) instead of `exemptions.py`'s calculation; `millage.py` uses them.
  - [x] Portability: modelled in projections (14% of homestead sales; law limit since 2026-10-16). Earlier note: revisit when projecting movers (not modelled explicitly for 2026). Roll: ~25% of 2025 homestead buyers ported, median $104,957 (`ASS_DIF_TRNS`).
- [x] **Calibration** (option A: modelled tax validated against official levies) — match modelled tax to reported `TAXAMT` and published levy totals
- [x] **Metrics** (`ptm/results.py`: deciles, Suits, replicate SEs) — distribution tables by income decile etc., Suits index, replicate-weight SEs
- [x] **Monroe County check** — fixed (shared PUMA merged Monroe with Miami-Dade); now 0.95 of roll. See CHALLENGES.md.
- [ ] **Putnam check** — model homestead tax 12% above the roll (218 records).
- [ ] **Under-$100k homesteads** — 9% below the roll since value-tenth ranking (small bills; low priority).
- [x] **City over-assignment** — fixed for Manatee (fire districts), Collier (authority lists) and small Lee fire districts: Bradenton 10.7k homesteads (was ~60k), Naples 6.6k (was ~100k). See CHALLENGES.md.
- [x] **Non-homestead owners' districts** — donors now restricted to non-homestead parcels owned by Florida-resident individuals (fallback: all owners). Marco Island non-homestead owners 26k → 20k (roll: 13k non-homestead parcels of all owners; PUMA-level limit). Also fixed the roll's out-of-state flag ("FLORIDA" spelled out in Broward, Palm Beach and two other counties).
- [ ] **Reprocess NAL rolls** so the stored `own_out_of_state` flag is correct (code now recomputes it from `own_state`).
- [ ] **More 2026 city rates** — Tampa, Orlando, Clearwater, Naples, Tallahassee, Gainesville, remaining Broward cities; replace proposed with final when DOR's 2026 Table 1 is out.
- [ ] **Escambia check** — 8% below the roll (814 records; 41 parcels missing JV).
- [x] **Public results display — the first public output** (agreed 2026-10-14). Draft built (private artifact): `ptm/results.py` → `scripts/results_2026.py` → `scripts/build_display.py` (`display/template.html`), styled after landeconomics.org. Next: county map, example households, "how the model compares" section; sharing is Daniel's call. Once the status quo is complete (owners only): a public page presenting Florida's current property tax by income decile, age, region and home type, with clear "owners only" labelling and links to LIMITATIONS. Plan the design together before building.
- [x] **Current-law projection** — 2026 → 2036 (step 2 below)
- [x] **Amendment 3** (Florida, Nov 3 2026 ballot) — first policy (page done 2026-10-16)
  - **Take-up setting** (built 2026-10-16, on by default, central 20%; superseded note: default off): "possibly eligible" non-claimers start claiming with probability rising in the benefit (bigger exemptions → more filers → bigger revenue loss). Show static and with-take-up results.
  - **Snowbird residency switch** (built 2026-10-16 as residency_switch, on by default; superseded note: default off): some likely-ineligible snowbirds move legal residency to Florida.
- [ ] **Ohio** (see Open items) — HB 920 reduction factors; Ramaswamy rollback-then-cap (rollback year as a setting)
- [ ] **Texas** (see Open items)

## Dropped: pass-through to renters
**Decided 2026-10-15 (Daniel): not doing rental pass-through.** Results stay owners only (the page says so); the settings switch keeps raising an error. Earlier notes kept for reference:
Decided 2026-10-14: model the status quo for **owners only** first; renters stay in the data labelled "not yet modelled"; income deciles defined over **all households**. The switch `Settings(include_rental_pass_through=True)` (`ptm/settings.py`) exists but raises an error until pass-through is built.

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

## Step 2: projection engine (started 2026-10-15)
- [x] **Economy paths** — `ptm/economy.py`, `inputs/fl_projection_assumptions.yaml` (editable), `inputs/fl_economy_paths.csv` (`scripts/fl_economy_inputs.py`). Home values: REC Ad Valorem adopted forecast (Aug 2026), existing residential appreciation excl. new construction, 2027-32; eased over 2033-36 to the EEC median sale-price path (~2.2%). Wages, other income, households: Florida EEC (July 2026). Scenarios: central, low (EDR proposal), high (FEA proposal), stall, downturn (Fed 2026 severely adverse shape); custom overrides (`source`, `set`, `shift`).
- [ ] **Inflation**: average CBO with Social Security Trustees and Philadelphia Fed SPF 10-year CPI (CBO 2.3% only for now); expose an inflation control to users.
- [ ] Regional/type variation in appreciation (condos, Southwest Florida) — first years from recent trends.
- [x] **Projection loop, pieces 1-2** — `ptm/project.py` (`Projection`): law indexing from the spec's `projection` rules (SOH cap = min(3%, prior-year CPI); second homestead exemption and income limits indexed); sales with Save Our Homes lock-in (2007 UF/Shimberg curve), reset rate 5.5% homestead / 8.4% other calibrated to the REC homestead differential forecast; portability (14% of homestead sales, own savings up to $500k; `portability_transfer` in `assess`). Central: owner tax $25.3B (2026) -> $30.6B (2030) -> $40.2B (2036) with 2026 rates held.
- [x] **Rate setting** — `ptm/rate_setting.py`: rule "history" (default) draws each government's yearly rate change from Florida's record (EDR ad valorem profiles: counties 1996-2025, cities 2009-2025, schools 1997-2025; `scripts/fl_millage_history.py`), capped at 110% of rolled-back except 3%/yr (2026 law); keep_capped / rolled_back / hold available. Jurisdiction bases: homestead from the model, other parts from economy paths, mix from 2026 rolls + Data Book.
- [x] **Monte Carlo** — `ptm/montecarlo.py`: noisy home value / non-residential / CPI paths x 200 rate draws, p10/p50/p90 by income decile. ~35 s for 20 paths on the laptop (5 workers).
- [x] **Deaths and age mix** — Florida 2021 life table (owner death without spouse resets; inside the calibrated reset rate); weights follow FDEC/BEBR population by age.
- [x] **New owners / new construction** — owners grow with EEC households; new homes at full value (recent-buyer donors placed by county new construction); NC out of rolled-back in year 1, then in the base.
- [x] Projection, remaining (2026-10-16: claims modelled; income-limited exemptions re-tested yearly; vote limits encoded): homestead status changes (claims/drops), re-test income-limited exemptions with indexed limits, regional/condo appreciation differences, max-millage tracking (ch. 2026-240), faster Monte Carlo (batch paths).
- [x] **Step 3**: projections and bands on the results page (baseline outlook).
- [ ] Check first projected years against REC taxable value forecasts.

## Municipality engine (revenue-neutral rates) — requested 2026-10-15
Modelled on the Maine property tax model's "Municipality Engine" (it re-solves each town's mill rate from the 2024 Municipal Valuation Return so municipal funding stays unchanged, accounting for state reimbursement of relief programs, e.g. Maine's homestead exemption and BETE reimbursements, and feeds the new rates back into the household engine). Florida version:
- [x] **Revenue-neutral response mode** (done 2026-10-15: `compare(..., response="revenue_neutral", reimbursement=r)`; page checkbox "Localities replace lost revenue"; 2027 checks: no non-school homestead tax -$12.1B vs -$13.5B with history responses, county mills +4.8; senior non-school: 65% of owners pay more). Only homestead value changes feed jurisdiction bases (non-homestead/non-residential follow economy paths), alongside (not replacing) "governments respond" (history) and "no response": each county, city and school district's rate under a policy = its current-law levy (net of state reimbursement) / its policy taxable base, every year. Bases already tracked by jurisdiction in `ptm/rate_setting.py` (2026 rolls + DOR Data Book).
- [x] **State reimbursement as a policy lever** (done 2026-10-16: page slider 0/25/50/75/100%; grid runs 25/50/75; government rates scale exactly by 1 - share). Still to do: share of each government's lost revenue the state pays (all, or by government type); include Florida's existing reimbursement for fiscally constrained counties (s. 218.12/218.125, EDR distributions) where relevant.
- [x] **Legal limits**: 10-mill cap on county general and city levies enforced by default in revenue-neutral mode, shortfall stays lost, toggle to ignore (2026-10-16). Still to do: MSTU/special district limits; governments whose re-solved rate would exceed the 10-mill caps or need a supermajority/referendum under s. 200.065.
- [x] **Per-government results** (done 2026-10-16: section 4 table of county general, city and school rates, current law vs policy): rate change for each county, city and school district (also the geography view).
- [x] **Page**: third series via checkbox in Policy comparisons; mode added to `scripts/policy_grid.py` ("neutral").
- [ ] Map of rate changes by government.
- [x] Feed non-homestead cap changes into jurisdiction bases (cap blocks, 2026-10-16).
- Estimate: 3-4 hours. Check Maine's model documentation for definitions to match (MVR fields, reimbursement rules).

## Amendment 3 page — requested 2026-10-15
- [x] (2026-10-16: "Amendment 3" view: whole amendment, larger exemption, 5% cap; five-year rule as written / struck down; revenue vs state estimate; policies in inputs/policies/amendment3*.yaml) A separate page (or view) with every change Amendment 3 makes, modelled against current law: read the amendment and implementing bill text, encode each provision as policy changes/levers, show the three outputs (new situation, changes, winners/losers) per provision and combined. Revenue-neutral mode (above) is relevant: local governments would need to replace lost revenue.
- [x] Amendment 3: read SB 4-F (ch. 2026-240): it changes s. 200.065 vote limits and re-enacts the fiscally constrained offsets; no elimination schedule or five-year-rule administration in it. Local options moved to Open items. Was: check SB 4-F (ch. 2026-240) implementing details (administration of the five-year rule, any elimination schedule the ballot summary mentions); local options (counties/cities raising the exemption; 2030 shortening of the wait).
- [x] Remove the double count of non-claimer owner-occupied homes in the non-owner tax estimate (2026-10-16).
- [x] Revenue lost (all property, rates unchanged; 10-year total; after responses; by government) leads the policy and Amendment 3 pages (2026-10-16).
- [x] Fiscally constrained county offsets as a revenue-neutral setting (s. 218.125 formula; 29 counties) (2026-10-16). Amendment 3: about $94M (2027), $174M (2031).
- [ ] Separate 10-mill caps for county-dependent districts and MSTUs (needs per-authority rates).

- [x] Revenue section: headline 'lost by Florida's local governments' and a 'for scale' line from statewide county and city Annual Financial Reports, FY 2023-24 (inputs/fl_local_finance_fy2024.yaml) (2026-10-16). Per-government revenue shares dropped: unadjusted county AFR files mix in custodial (pass-through) taxes.
- [ ] (optional) Compare Amendment 3 county/city/special district impacts with REC's per-government tables (impact0710.pdf pages 5-18) to see where the model differs.
- [x] Homestead status changes in response to policy: take-up by possibly-eligible non-claimers and second-home residency switching, on by default, static run kept for comparison (2026-10-16). Still to do: settle the central values (Texas 2023 evidence); un-claiming when exemptions shrink; switching in city bases and history-mode rate responses.

