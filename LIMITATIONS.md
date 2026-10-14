# Model limitations

What the model can't do, or does only approximately. Read this before citing results.
`CHALLENGES.md` covers problems we've *solved or are solving*; this file covers what remains true of the results even after those fixes. Entries marked **(being reduced)** have planned work that will narrow them.

---

## Data: who's in the model

- **Sample, not census.** PUMS is ~1% of households (Florida: 87,327 household records, 65,784 owners). Estimates for small groups or small areas are noisy; report standard errors from the 80 replicate weights.
- **2024 survey, 2026 base year.** Households are surveyed in 2024 and brought forward. Values and incomes are aged; the mix of households is mostly not, apart from reweighting for new construction. People who moved to, left, or formed households in Florida after 2024 are represented only through those weights. **(being reduced:** new-development reweighting by PUMA**)**
- **Self-reported values and taxes.** Home value (`VALP`) is the owner's estimate; property tax (`TAXAMT`) is what they report paying. Both contain error.
- **$0 reported tax.** Most $0 reports are real (veterans' total exemption, rented-lot mobile homes, cheap homes); ~69,000 owners are classed as misreported and will get a modelled tax. Which individual households are which is an estimate.
- **Special exemptions are imputed.** Veterans', disability and senior exemptions match the roll's counts by area, but PUMS can't identify 100% permanently disabled veterans or surviving spouses exactly; some $0 reporters without veteran signals carry the veterans' exemption so totals match. Results for policies that change these specific exemptions should be read with that in mind. Low-income senior eligibility uses income minus Social Security as a stand-in for adjusted gross income. The $5,000 widow/widower/blind/disabled and disabled ex-service exemptions aren't assigned yet.
- **Granny-flat reductions aren't modelled.** Florida lets counties reduce the assessed value of a home where quarters were built for a parent or grandparent 62+ (s. 193.703; up to the lesser of the added value and 20% of the home's assessed value). Only 702 parcels statewide have it (2026 roll; median reduction 19% of assessed value), and PUMS doesn't record construction for parent quarters, so it isn't assigned to any household. Effect on statewide results is negligible; studies of multi-generational housing specifically would need it (assign to owner households with a parent or grandparent 62+ present, matched to roll counts).
- **Portability isn't applied household by household.** PUMS can't see a mover's previous homestead, so the $500k transfer of Save Our Homes savings isn't calculated directly. In the 2026 baseline its effect is included through assessment gaps drawn from real roll parcels (which carry ported savings); projections of future movers will need it explicitly.
- **Top-coding.** PUMS replaces the most expensive homes and largest tax bills with a single amount. Florida home values are now imputed from the parcel roll's real top homesteads (`ptm/topcode.py`): the distribution of top values is right by region, but which top-coded household gets which value is an estimate (guided by reported tax). Top-coded tax bills ($42,500) are still the floor amount until tax rates are calibrated. **(being reduced:** top-coded tax at calibration**)**
- **Income top-coding.** High incomes are top-coded by component, so the very top of the income distribution is understated.
- **Income is one year's income.** PUMS measures annual income, not wealth. "House-rich, cash-poor" owners — especially retirees — look poorer than they are; tax as a share of income overstates their burden in that sense.

## Data: tax details

- **Homestead status is imputed.** PUMS has no homestead flag. Counts match the parcel roll by area and home type, and households are chosen mainly by whether their reported tax looks like a homestead's — but any individual household's status is a best guess. Reasons we can't see (LLC title, spouse claiming elsewhere) are assigned at random.
- **Take-up response.** If exemptions grow, eligible owners who haven't filed may start claiming. The model handles this only through a setting (off by default), so static results understate the cost of larger exemptions.
- **Imputed, not observed, tax details.** Assessed value (the Save Our Homes gap), exemptions and land value come from similar parcels in the same area and value band. They are right for groups (income deciles, age groups, regions) but not for any individual household.
- **No exact location for households.** PUMS only gives the PUMA (~100,000 people). Local tax rates vary within PUMAs, so household tax rates are approximations calibrated to totals.
- **"Just value" vs market value.** The roll's just value may be systematically below market value (Florida's cost-of-sale adjustment, to be confirmed), which affects comparisons with PUMS values.
- **Preliminary rolls.** Some counties' 2026 parcel data is preliminary; final values can differ slightly until we rerun with final rolls.
- **Owner linking by name.** Anonymous owner IDs match on name spelling, so individuals with several homes recorded under different spellings are undercounted. Works best for companies.

- **2025 tax rates on 2026 values.** 2026 district rates aren't published statewide yet; 2025 final rates are used until they are. Where values fell, 2026 rates are probably a little higher.
- **Tax district is imputed.** Each household gets the district of a real parcel in its PUMA with similar value (guided by its reported tax), not its own. Right for areas, not for individual homes.
- **A few counties' rates are reconstructed or incomplete:** Orange (district composition rebuilt from authority rates), Sarasota (2026 composition), Gadsden and Liberty (components only), Broward letter-suffix districts (missing small special-district levies).
- **Flat fees aren't in modelled tax.** Non-ad valorem assessments (fire, solid waste, stormwater) are on bills but aren't property tax (not rate × value) and are excluded. Modelled tax won't match what households report: survey-reported tax differs from official-rate modelled tax by county (South Florida reports less, parts of Central/Southwest Florida more); the model follows official levies, which it matches within ~5%.
- **Levy classes are approximate below the county level.** Each district's millage is split into school, county and municipal from official rates; independent special districts and water management districts are lumped into "county" for now, so county-only senior exemptions are slightly over-applied (about $20/yr for affected seniors).

## Scope: what's not modelled

- **Residential property only.** No commercial, industrial, agricultural or tangible personal property. Revenue results cover the residential base; policies that shift tax onto other property types aren't fully captured.
- **Renters' burden.** For now, results show nominal property tax only. How much of landlords' tax reaches renters (pass-through) is not yet modelled, so renters appear to pay nothing. **(being reduced:** pass-through options in `TODO.md`**)**
- **Mobile homes on rented lots** pay lot rent rather than real-estate tax; their indirect burden is part of the pass-through question.
- **Owners who don't live in Florida.** Second homes and investor-owned property are in the parcel data (and count toward revenue), but their owners aren't Florida households, so their gains and losses appear only as a separate non-household line.

## Behaviour: what's held fixed

The model is **static**: it applies the rules to households as they are. It does not model:
- **Capitalization** — tax cuts or increases changing home prices.
- **Moving** — people moving in, out or within the state because of tax changes (e.g. Save Our Homes lock-in).
- **Local government responses** — cutting services or raising rates to replace lost revenue, except through explicit scenario settings.
- **Construction responses** — builders responding to tax changes.
- **Landlord pricing** beyond whatever pass-through assumption is chosen.

## Projections (2026–2036)

- Future house-price growth, income growth, new construction and inflation are **assumptions**, not forecasts. Results years out depend on them; show sensitivity to them.
- Tax rules are applied as written. Future legislation, court rulings, or changes in how assessors apply the law aren't anticipated.
