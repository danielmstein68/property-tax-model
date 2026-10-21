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
- **Local rate setting in projections (Daniel, 2026-10-21: keep each unit's 2025 position).** Was: every unit at its voter-approval rate. Now each unit keeps where it set its 2025 rate between its no-new-revenue and voter-approval rates (Comptroller 2025 rates and levies; levy-weighted position 0.54 counties, 0.57 cities, 0.57 colleges, 0.65 hospitals, 0.94 special districts), applied to the M&O rate: no-new-revenue M&O x (1 + position x (multiplier - 1)), multiplier 1.035 (1.08 hospital districts and colleges); debt rates held. Monte Carlo paths redraw positions each year from each class's 2025 spread. Why: real behaviour; all-at-voter-approval overstated growth. Options kept: voter_approval, hold.
- **School funding in projections (provisional).** Entitlements, weighted students and the basic allotment are held at 2026-27 levels (current law), so as values rise state aid falls and recapture rises (state aid $24.6B in 2026-27 to $16.3B by 2036 in the central case). The Legislature resets funding every session, so the school-finance path is a current-law benchmark, not a forecast.
- **Households in projections (2026-10-21, Daniel: "make sure TX has everything Florida does").** Replaces "households fixed". Same pieces as Florida, plus explicit ageing (Florida keeps records' ages and only reweights):
  - *Ages:* every owner ages a year; the older of householder and spouse sets over-65 status (s. 11.13(c)).
  - *Turning 65 (provisional):* owners reaching 65 claim the over-65 exemption, the units' local over-65 amounts and a freeze at that year's tax (schools; counties, cities and colleges that have adopted one) at the 2026 claim rate of owners 65+ (88.6%; counts were trimmed to the PVS over-65 exemption).
  - *Sales and deaths (provisional):* 5.6% of homes a year change hands (PUMS 2024 move-ins, MV 1-2), lowered by cap savings with Florida's lock-in estimate (no Texas estimate); deaths from the Texas 2021 life table (both spouses for couples) count inside that rate. The home resets to market and gets a new owner drawn from the county's recent buyers (age, income, over-65/disabled status, over-65 at the same claim rate); the old freeze ends. Not modelled: ceiling portability, veterans' status changing with a sale (it stays with the home).
  - *Age mix and new owners (Daniel, 2026-10-21: keep household growth with the TDC age bands in the baseline):* owners by householder age (18-64, 65+) grow with Texas's projected population in each band (Texas Demographic Center Vintage 2024, mid migration: 2020, 2040, 2060 from TDC's Oct 2025 webinar, rounded to 0.1M, interpolated), i.e. constant ownership rates by band. Owners grow about 1.7% a year, homesteads 6.24M (2026) to 7.56M (2036). The extra owners are new homes at full value (recent buyers' records, placed by county with TDC's projected county growth). TDC's full age file is behind a sign-up form; the webinar numbers stand in until Daniel fills it in or OKs skipping it.
  - *Incomes (provisional):* wages and other income grow with Texas personal income per resident (Comptroller CRE 2026-27: 4.6% 2026, 4.8% 2027), easing over four years to 3.6% (CBO CPI 2.3% plus about 1.3 points of real growth); Social Security, SSI, assistance and pensions with CPI (CBO). Inputs: scripts/tx_economy_inputs.py.
  - *Other property (provisional):* each unit's non-homestead taxable value (2025 roll less the model's owners, grown 3.6% to 2026) grows with its county's PVS mix of residential, business and mineral value (business with home values, minerals flat) plus 1.5% new construction; the circuit breaker's 2025 loss comes back in 2027 when it expires. This gives total property tax by year (2026: $90.6B, vs $89.5B levied in 2025).
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

## Law check against the full text (2026-10-21, Daniel: "download the full Texas Property Tax Code ... and check the encoded rules")

Downloaded to `data/raw/tx_law_text/`: Tax Code Title 1 (chapters 1, 5, 6, 11, 21-26, 31-34, 41-43: the whole Property Tax Code), Constitution art. VIII, Water Code ch. 49, Education Code ch. 130, Health and Safety Code chs. 281 and 286 (with the earlier Education Code chs. 45, 46, 48, 49 and Government Code ch. 403).

Matches the text: 10% homestead cap (s. 23.23); 20% circuit breaker, $5.32M threshold for 2026, expiring Dec 31, 2026 (s. 23.231(k)); school homestead $140,000 (s. 11.13(b); Const. art. VIII s. 1-b(c)); over-65/disabled $60,000 (s. 11.13(c)) for the whole year a person qualifies (s. 11.42(c)); local percentage up to 20%, at least $5,000 (s. 11.13(n)), no cut for 2022 adopters until 2027 (n-1); local over-65 at least $3,000 (s. 11.13(d)-(e)); county farm-to-market $3,000 (s. 11.13(a)); disabled veterans $5,000-$12,000 (s. 11.22); local freezes fixed in dollars at the first year's tax (s. 11.261(b)); voter-approval 1.035 / 1.08 (s. 26.04(c)(2)).

The rules file was right but the projection code didn't follow it in three places (fixed):
- **School compression growth.** Each district's MCR falls when its total taxable value (DPV, new property included) grows 2.5% or more (Ed. Code s. 48.2551(b)); the state percentage uses statewide total growth (s. 48.255(b)). The code used existing-home appreciation only. Now each district's modelled taxable growth (homesteads plus its non-homestead base with new construction), which also sets school finance values. Central 2036 state MCR $0.5811 -> $0.4617; homestead tax 2036 $54.7B -> $51.4B (10th-90th percentile $44.4-57.4B); all property tax 2036 $147.6B -> $139.0B; state school aid 2036 $16.3B -> $18.4B.
- **School freeze ceilings ratchet** (s. 11.26(a-10)): the ceiling is last year's tax *imposed* less last year's taxable value x the MCR cut, less any increase in the $140k/$60k exemptions x this year's rate (needed for policies). The code carried the ceiling forward without resetting it to the tax imposed.
- **Special taxing units** (s. 26.012(19)): any non-school unit with M&O of 2.5 cents or less gets 1.08, not only hospital and college districts (716 of 4,578 units).

Not modelled (logged): water districts' developed / developing status (Water Code ss. 49.23602-.23603; all non-low-rate districts at 1.035) and that their limit is on the average homestead's tax; unused increment and de minimis rates; ceiling portability (s. 11.26(g)); tax deferral for over-65 owners (s. 33.06; affects collections, not levies).
