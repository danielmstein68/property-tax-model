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
