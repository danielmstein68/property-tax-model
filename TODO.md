# To do

Steps we're working through one at a time. Each gets discussed before it's built.

## In progress
- [ ] **Load Florida PUMS** (2024 1-year housing file) — `ptm/load.py`

## In progress (running)
- [ ] **Florida parcel rolls, all 67 counties** — `scripts/fl_parcels.py`; checks in `data/processed/fl_nal_2026/_checks.csv`

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
- [ ] **Age to 2026** — bring 2024 values, incomes and rents forward to the 2026 base year
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
