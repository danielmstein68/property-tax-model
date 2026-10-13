# Model limitations

What the model can't do, or does only approximately. Read this before citing results.
`CHALLENGES.md` covers problems we've *solved or are solving*; this file covers what remains true of the results even after those fixes. Entries marked **(being reduced)** have planned work that will narrow them.

---

## Data: who's in the model

- **Sample, not census.** PUMS is ~1% of households (Florida: 87,327 household records, 65,784 owners). Estimates for small groups or small areas are noisy; report standard errors from the 80 replicate weights.
- **2024 survey, 2026 base year.** Households are surveyed in 2024 and brought forward. Values and incomes are aged; the mix of households is mostly not, apart from reweighting for new construction. People who moved to, left, or formed households in Florida after 2024 are represented only through those weights. **(being reduced:** new-development reweighting by PUMA**)**
- **Self-reported values and taxes.** Home value (`VALP`) is the owner's estimate; property tax (`TAXAMT`) is what they report paying. Both contain error.
- **$0 reported tax.** 5.6% of Florida owners report no property tax. Many are real (mobile homes on rented lots, exemptions on cheap homes), but ~150,000 households with homes over $200k are hard to explain and may be misreported. **(being reduced:** compare with parcel data by value band**)**
- **Top-coding.** The most expensive homes and largest tax bills are replaced by a single amount. Totals at the top appear roughly right; the spread among top homes is lost. **(being reduced:** Pareto tail fitted to parcel data**)**
- **Income top-coding.** High incomes are top-coded by component, so the very top of the income distribution is understated.
- **Income is one year's income.** PUMS measures annual income, not wealth. "House-rich, cash-poor" owners — especially retirees — look poorer than they are; tax as a share of income overstates their burden in that sense.

## Data: tax details

- **No homestead flag in PUMS.** All owner-occupied homes are treated as homesteads.
- **Imputed, not observed, tax details.** Assessed value (the Save Our Homes gap), exemptions and land value come from similar parcels in the same area and value band. They are right for groups (income deciles, age groups, regions) but not for any individual household.
- **No exact location for households.** PUMS only gives the PUMA (~100,000 people). Local tax rates vary within PUMAs, so household tax rates are approximations calibrated to totals.
- **"Just value" vs market value.** The roll's just value may be systematically below market value (Florida's cost-of-sale adjustment, to be confirmed), which affects comparisons with PUMS values.
- **Preliminary rolls.** Some counties' 2026 parcel data is preliminary; final values can differ slightly until we rerun with final rolls.
- **Owner linking by name.** Anonymous owner IDs match on name spelling, so individuals with several homes recorded under different spellings are undercounted. Works best for companies.

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
