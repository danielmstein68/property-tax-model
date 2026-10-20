# Texas model: decisions log

Decisions Daniel made (2026-10-20) and the provisional calls made while building, each with the reason.
Small calls are marked **(provisional)** for Daniel to review at the end; big decisions go to him by email first.

## Made by Daniel (2026-10-20)

| Question | Decision |
|---|---|
| Parcel data | Bulk roll files from the largest appraisal districts (about 12, ~60% of homesteads); the rest of the state calibrated to the Comptroller's school-district totals (Property Value Study). |
| School finance | Full school funding formula, district by district (maximum compressed rate, tier one and two, recapture, state aid that holds districts harmless for exemptions and compression). |
| Policies to compare | Decided after the 2026 baseline and the projections to 2036 are built. |
| Page | The same artifact as Florida, opening with "Select a state". |
| Base year | Tax year 2026: July 2026 certified rolls, 2026 adopted rates, 2026-27 school funding. Gaps filled with 2025 rates and flagged. |
| Value forecasts | Legislative Budget Board / TEA property value growth assumptions behind the 2026-27 school funding estimates, then Texas home price trends easing to long-run growth by 2036; same five scenarios and Monte Carlo range as Florida. |
| Coverage | Same as Florida: owner households by income decile (renters at $0 in all-household results); rentals, business and mineral property in tax bases and revenue, not as households. |
| Check-ins | Email (danielm.stein68@gmail.com) at milestones, when blocked, and for any big decision; small calls logged here. |

Milestones: (1) data collected, (2) law encoded, (3) 2026 baseline checked, (4) projections to 2036 done.

## Provisional calls while building

- **Circuit breaker lapses in the baseline (provisional, in milestone 1 email).** The 20% cap on non-homestead real property up to $5.32M (Tax Code s. 23.231) expires Dec 31, 2026 and no 2025 bill extended it. Baseline follows current law: no cap from 2027. Extending it is a policy option. Why: the baseline is current law, as in Florida.
- **Code layout (provisional).** Texas-specific code in `ptm/tx/` (rolls, taxing units, exemptions, freezes, school finance); shared pieces (PUMS loading, results, Monte Carlo, comparisons) reused from `ptm/`. Why: Florida's engine is written around Florida's levy classes; Texas taxes by taxing unit with per-unit exemptions and freezes.
- **"Disabled" for the over-65/disabled exemptions (provisional).** The law means eligible for Social Security disability (s. 11.13(m)). Proxy: under 65 with an ACS disability and Social Security or SSI income. Why: closest survey match; calibrated to the rolls' counts where the rolls show over-65/disabled exemptions.
- **School compression after 2026 (provisional).** Baseline MCRs follow the current-law formula (2.5% value-growth limit, state compression percentage from the GAA's value growth) with no new compression; more compression is a policy option. Why: current law.

- **Homestead counts without a roll (provisional).** The 2024 value study's count grown 3% to 2026 (the 2026 rolls run 2.4-4.8% above 2024); the 2025 study undercounts some districts (Tarrant 374k vs 412k in 2024 and 422k on the 2026 roll). Counties with a roll use the roll.
- **Homestead PVS counts.** Counted from the value lost to the $10,000 step of the school exemption (almost no home is worth less), matching the Comptroller research note (Harris 850,527 in 2024).
- **Local exemptions outside the roll counties: asked Daniel by email (2026-10-20), building on option A meanwhile.** Counties, cities, colleges and special districts set their own homestead % and over-65 amounts; no statewide list exists. Option A: typical values by unit type from the roll counties (school districts: each district's own local-option loss from the PVS), with county results outside roll counties labelled approximate. Alternatives: none (B), hand collection (C), or the Comptroller EARS records request (D, recommended alongside A).
- **Taxing units outside the roll counties (provisional).** County: the household's county. School district: drawn by PVS homesteads per district within the county. City: in a city with probability = the county's city market value / county market value, the city drawn by market value. Colleges, hospital and special districts: their market-value-weighted average rate across the county.
- **Freezes (provisional).** Tarrant's and Harris's files carry no freeze ceilings; school freezes are calibrated to the PVS over-65 freeze loss.
- **Projection value growth (provisional).** No official Texas value forecast exists past tax year 2026 (GAA 3.60%). Central: +1.5% (2027), +2.5%, +3.0%, then 3.5% a year; low, high, stall and downturn scenarios (inputs/tx_projection_assumptions.yaml). Replace with LBB/TEA numbers when the January 2027 budget cycle publishes them.
- **Local rate setting in projections (provisional, worth Daniel's view).** Cities, counties and special districts adopt their voter-approval rate (M&O revenue on existing property +3.5%; +8% hospital and college districts); debt rates held. The alternative is holding rates (revenue grows with values).
- **School funding in projections (provisional).** Entitlements, weighted students and the basic allotment are held at 2026-27 levels (current law), so as values rise state aid falls and recapture rises (state aid $24.6B in 2026-27 to $16.3B by 2036 in the central case). The Legislature resets funding every session, so the school-finance path is a current-law benchmark, not a forecast.
- **Households fixed in projections (provisional).** No new homes, sales only reset the cap (5% a year); per-homestead results are the focus.
- **Owners without a homestead exemption (provisional).** Taxed at full value with no exemptions, at their county's median combined homestead rate (they have no roll donor yet).
- **Freezes calibrated to TEA (2026-10-20).** Only El Paso's and Travis's rolls carry school freeze ceilings, so the model's school M&O on over-65/disabled homesteads ran at 1.93x TEA's frozen levy (ACTUAL_FROZEN_LEVY, 2026-27 SOF). Each district's over-65/disabled school tax is now scaled by TEA frozen levy / model uncapped levy (at most 1; small districts take the statewide ratio): 1.107x after. Homestead tax 2026 $30.6B -> $29.1B.

## Statewide check (scripts/tx_validate_2026.py, 2026-10-20)
Model vs Comptroller PVS 2025 final (same $140k/$60k exemptions) and TEA:
- homesteads 0.984; state homestead exemption (sum of min(appraised, $140k)) 1.044; frozen school M&O levy 1.107
- over-65/disabled school exemption 1.19 (roll counties 1.23): too many over-65/disabled, or their values too high; likely the over-65 inference from exemption amounts in roll counties (it also catches local school exemptions). Tax effect about 0.6%. Open.
- 100% disabled veterans 1.22 (roll counties 1.77): the rolls' total-exemption flags count more homes than the PVS dollar total implies. Tax effect about 0.5%. Open.

## Accuracy round 2 (2026-10-20, Daniel: "do whatever you need to make things accurate")
- **Value anchor outside the roll counties.** Each county's homestead market total = R x its PVS 2025 A+E+M market value, R = median over roll counties of homestead market / that total (0.65-0.82, median ~0.77).
- **Over-65/disabled trimmed to official counts.** Roll counties: the roll's flagged count (model had Dallas 198k vs 157k); elsewhere the PVS over-65 school exemption. Statewide check 1.19 -> 0.95.
- **100% veterans.** The PVS records the veterans' exemption net of the $140k homestead (rolls match it at 0.996 that way); non-roll targets now use that. Statewide 1.22 -> 0.89.
- **Non-homestead owners** taxed from non-homestead roll parcels of Texas-resident owners (no homestead exemptions).
- **Bell County roll** added (ten rolls).
- **2026 school rates** from TEA's 2026-27 Summary of Finances in the production build (checks keep 2025 rates on both sides).
- **Local exemptions collected for 17 counties without a roll (2026-10-20, option C, Daniel: "do whatever you need").** inputs/tx_local_exemptions_<county>.csv from appraisal districts' and tax offices' published unit tables: Bexar, Montgomery, Hidalgo, Brazoria, Nueces, Lubbock, Hays, Comal, McLennan, Smith, Kaufman, Johnson, Guadalupe, Jefferson, Gregg, Wichita (official), Hunt (title-company chart, unofficial). 607 units matched to the Comptroller's. Not found: Denton, Cameron, Ellis, Webb, Randall. Gaps: flat "+$3,000" road-levy add-ons not captured; Hidalgo's school amounts predate the 2025 increase (only the local part is used); some freeze flags blank (non-school freezes aren't modelled yet).
- **Leave-one-out after the value anchor and count fixes (before the collected exemptions):** Tarrant 1.289 -> 1.004, Travis 1.065 -> 1.011 of roll tax when treated as if it had no roll (Travis city tax still 1.28: borrowed local exemptions).
- Result: homestead tax 2026 $29.5B; owners $34.4B; 2036 central $44.0B.
