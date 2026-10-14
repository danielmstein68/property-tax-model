# Challenges

Every data or modelling problem we've hit, and how we solved it (or plan to). When adding a state, read this first: most issues will come up again.

Status: **Solved**, **Planned** (decided, not built yet), **Open** (not decided).

---

## All states (ACS PUMS)

### Aggregates can be right while distributions are wrong
- **Problem:** from earlier Maine work. PolicyEngine's Populace microdata built Maine from reweighted national donor households: it hit Maine's totals but had no owners owning free and clear (42% in reality) and 70% of owners with no tax bill (2% in PUMS). Every question here is distributional, so that kind of data isn't usable.
- **Solution (principle):** PUMS respondents stay the base, with their observed `TAXAMT`, `HINCP`, `TEN`. Anything we add must not flatten them:
  - **Imputation from parcels:** draw from similar parcels (donors), don't assign cell averages, so each household keeps realistic variation (e.g. in the Save Our Homes gap).
  - **Calibration:** keep reweighting light and check distributions before vs after, not just totals — free-and-clear share, $0-tax share, tax by income decile, owners 65+.
  - **Observed tax is an anchor:** calibrate modelled tax to reported `TAXAMT`; don't silently overwrite it.
  - **Sample size:** Florida has 65,784 owner records (mean weight ~95). Keep imputation cells coarse enough not to run thin.

### Latest PUMS year not released yet
- **Problem:** in October 2026 the 2025 1-year PUMS isn't on the Census server (the 2024 files are dated December 2025, so releases are running late).
- **Solution (Solved):** use 2024 1-year and age it to the 2026 base year. Check `https://www2.census.gov/programs-surveys/acs/data/pums/` for newer years before starting a state.

### 1-year vs 5-year PUMS
- **Problem:** the 5-year file has ~5× the sample, but it's a pooled cross-section, not a panel, and its dollars are adjusted with CPI. House prices rose much faster than CPI in 2020–2024, so older records' home values are understated.
- **Solution (Solved):** use the 1-year file for statewide results. If sub-state detail is needed, switch to 5-year and age each record from its own survey year (first 4 characters of `SERIALNO`) with a house-price index.

### 2020 1-year data is experimental
- **Problem:** the pandemic disrupted 2020 collection; the Census Bureau only released experimental 1-year estimates.
- **Solution:** don't use 2020 1-year files.

### PUMA boundaries changed in 2022
- **Problem:** files from 2022 on use 2020-census PUMAs; earlier files use 2010 PUMAs.
- **Solution (Planned, if needed):** crosswalk with Geocorr (Missouri Census Data Center), or compare at geographies that didn't change (state, metro).

### PUMS has no county
- **Problem:** the smallest geography is the PUMA (~100k people). Big counties contain several PUMAs; small counties are grouped together into one PUMA. Property tax is set locally, and parcel data comes by county.
- **Solution (Solved, mapping):** Census tract-to-PUMA relationship file (`2020_Census_Tract_to_2020_PUMA.txt`) gives each PUMA's county or county group; county names from `st<FIPS>_<st>_cou2020.txt`. Both from `www2.census.gov/geo/docs/`. Florida: 168 PUMAs → 44 counties or county groups.

### Which dollar adjustment applies to what
- **Problem:** `ADJINC` and `ADJHSG` apply to different variables, and it's easy to apply them to the wrong ones.
- **Solution (Solved):** per the 2024 data dictionary, `ADJINC` applies to income (`HINCP`, `FINCP`, person income), `ADJHSG` applies to housing costs (`RNTP`, `GRNTP`, `SMOCP`, ...). **Neither applies to `VALP` or `TAXAMT`.** Both factors have 6 implied decimals. Implemented in `ptm/load.py`.

### New development and uneven change since the survey year
- **Problem:** PUMS misses homes built after the survey, and values changed unevenly by area, type, price tier and storm damage. Florida 2026 roll: homes built 2024–25 range from 0.4% of homes (Broward) to 8.0% (Charlotte). New homes have no assessment-cap gap, so their owners face very different tax.
- **Solution (Planned):** reweight PUMS households in recently built homes (`YRBLT`) by PUMA to match the roll's count of new homes (`ACT_YR_BLT`); age values by area × type × tier, ideally from the same parcels' values in two rolls (request older rolls). Never use one statewide factor.

### Linking parcels to PUMAs: `CENSUS_BK` formats vary by county
- **Problem:** 8.8% of parcels don't match a 2020 tract. Some counties store `CENSUS_BK` in scientific notation (Taylor), with an extra digit (Martin), or with 2010-era tract codes (Collier, Highlands, Okeechobee).
- **Solution (Solved):** unmatched parcels fall back to their county (DOR county number → FIPS: 2 × (DOR − 11) + 1, except Miami-Dade = 086) and are spread over the county's PUMAs in proportion to matched parcels (`fl_dor_to_fips`, `fl_parcel_puma` in `ptm/geo.py`). Could later repair formats county by county.

### Top-coded home values and taxes
- **Problem:** the most expensive homes are replaced by one state-specific amount, which only says the real value is "at least" that. These homes pay a large share of tax.
- **Solution (Planned):** fit a Pareto tail and give each top-coded home its own value (random draws, fixed seed).
  - **Method B (preferred, where parcel data exists):** fit the tail to the real distribution of values in the state's parcel tax roll.
  - **Method A (fallback, when no usable parcel data):** fit the tail using only PUMS homes just below the cut-off, constrained so the draws average the top-coded amount (if the Census Bureau sets it to the mean above the cut-off — still to confirm). Validate against any published totals available.
- **Detection:** top-coded records are the ties at the column maximum (`flag_topcode_valp`, `flag_topcode_taxamt`).

### Top-coded income
- **Problem:** household income (`HINCP`) isn't top-coded itself; its components (wages, investment income, ...) are top-coded per person. So the tie-at-max test doesn't work for income.
- **Solution (Open):** either drop the income flag and note the limitation, or detect component top-codes in the person file.

### Owners reporting $0 property tax
- **Problem:** some owners report $0 tax. It may be real (exemptions) or misreporting (escrow payers who don't know).
- **Solution (Open):** examine by home value, building type and state exemptions before calibration. Flagged as `flag_zero_taxamt`.

### No homestead / primary residence flag
- **Problem:** PUMS doesn't say whether an owner claims a homestead exemption. Florida: 6.35M PUMS owner households (2026 weights) vs 5.21M homestead parcels — ~1.1M owners don't claim.
- **Why (roll evidence):** of 3.05M non-homestead single-family/condo/co-op/mobile parcels, 1.39M have out-of-state owners, 348k Florida businesses (LLCs can't claim), 434k Florida individuals mailing to a different ZIP, **719k Florida individuals mailing to the same ZIP** (likely owner-occupied non-claimers), 152k unknown ZIP. Reasons: mobile homes on rented lots (~290k; not real property); snowbirds counted as Florida households by the ACS 2-month residence rule but homesteaded elsewhere; non-permanent residents (ineligible); LLC/corporate title; recent buyers not yet filed; never applied.
- **Solution (in progress):** mobile homes first (Solved: `assign_mobile_home_lots`); then assign the remaining non-claimers to match roll counts by PUMA × type × value band, tilted by PUMS signals (Planned).

### Renters' share of property tax (pass-through)
- **Problem:** renters pay landlords' property tax indirectly; how much is an assumption.
- **Solution (Open, deferred):** nominal tax only for now. Options in `TODO.md`.

### Residential only
- **Problem:** PUMS has no commercial, industrial or farm property, so revenue estimates cover only part of the tax base.
- **Solution (Planned):** calibrate to published residential levies; report the share of the total base covered.

### Aging incomes: by type, and missing months
- **Problem:** income types grow at different rates (2024→2026 Florida: wages +9.8%, Social Security +5.4%, CPI +6.0%), so one factor misstates older households' income. Also, October 2025 CPI was never published (government shutdown), and 2026 isn't over.
- **Solution (Solved):** age each person's income components separately and re-sum to households (`ptm/aging.py`); factors compare the same calendar months (or quarters) in both years and skip unpublished ones (`scripts/aging_factors.py`). Checks: components sum to `PINCP` and persons sum to `HINCP` for 100% of records. Result: median income +9.8% for householders under 45 but +6.1% for 75+.

### Which wage growth measure
- **Problem:** measures disagree for Florida 2024→2026: CES average hourly earnings +12.1% (5.9%/yr), CES average weekly earnings +12.7%, QCEW average weekly wage +9.8% (4.8%/yr), US average hourly earnings +7.5%. Florida jobs grew only 0.9%, so job-mix changes may inflate survey averages.
- **Solution (Solved):** use QCEW (every UI-covered job, not a survey sample), comparing the same quarter in both years. It lags ~6 months; rerun as quarters are published.

### Census data API needs a key
- **Problem:** `api.census.gov` now redirects keyless requests to a "Missing Key" page, so published figures can't be pulled automatically without one.
- **Solution (Open):** get a free key at https://api.census.gov/data/key_signup.html and store it in an environment variable (`CENSUS_API_KEY`), never in the repo.

---

## Florida

### Save Our Homes: tax reflects assessed value, not market value
- **Problem:** homestead assessed value can rise at most 3% or CPI a year (whichever is lower) and resets on sale. Long-time owners' assessed values sit far below market, so tax ÷ rate understates market value. "Portability" lets movers carry up to $500k of the gap to a new home.
- **Solution (Planned):** use `MV` (move-in year range) to model the gap; calibrate the gap by value band against parcel data (assessed vs just value). For value cross-checks from tax, use recent movers only.

### Homestead exemption differs for school and non-school taxes
- **Problem:** first $25k is exempt from all levies; the second $25k band (indexed for inflation) is exempt from non-school levies only. Amendment 3 also only changes non-school exemptions.
- **Solution (Planned):** compute school and non-school taxable value separately.

### Top-coding amounts (2024 1-year)
- Home value: **$6,471,000** (706 records, 0.8% of owners).
- Property tax: **$42,500** (735 records).
- Either: 1.3% of owner households but **10.6% of reported owner tax** and 12.2% of value.
- **Solution:** Method B using the Florida DOR parcel tax roll (see above).
- **Finding (Miami-Dade):** $6,471,000 is the *replacement* amount, not the cut-off. PUMS has ~8,900 top-coded owner homes in Miami-Dade PUMAs; the 2026 roll's top ~8,500–8,900 homesteads start at about $2.9–3.0M and average $6.35–6.54M — almost exactly the replacement amount. This supports the replacement being the mean above a ~$3M cut-off, so PUMS totals at the top are roughly right; only the spread is lost. (Rough: different years, and PUMS is self-reported market value vs the roll's just value.)

### Owners' reported tax with $0
- 3,700 records, 347k households (5.6% of owners). Profile vs owners who pay tax:
  - median home value $125k vs $400k; 45% under $100k vs 6%;
  - 41% mobile homes vs 6% (28% of mobile-home owners report $0);
  - 62% own free and clear vs 43% — so "escrow payers who don't know their tax" explains little;
  - 46% householder 65+ vs 40%; median income $60k vs $93k.
- **Two groups:**
  - **Under $200k (~57%), mostly plausible.** Mobile homes on rented lots generally aren't taxed as real property (owner registers the home; the park owner pays the land tax), and the homestead exemption wipes out most tax on very cheap homes. Low-income senior and disability exemptions add more.
  - **$200k+ (~150k households, 43%) — hard to explain** with standard exemptions. Possible: veterans' total-disability exemption, the local-option long-term low-income senior exemption, or misreporting.
- **Plan (Planned):** once the parcel roll is in, compare the PUMS $0 share by value band with the share of homestead parcels with $0 taxable value. Treat the excess as misreporting and impute tax for it; keep the rest as real. Mobile homes on rented lots need their own treatment (relevant to renter/landlord incidence too).

### Home values fell 2024 → 2026, very unevenly
- **Finding (Zillow ZHVI, 2024 avg → Dec 2025):** median county −4%; condos −12% (to −25% in Charlotte); bottom tier −6% vs top −3%; Southwest Florida worst (Charlotte −17%, Lee −13%). Under Save Our Homes, assessed values keep rising by the cap while below market, so long-time owners' bills rose ~5.7% while values fell — but recent buyers' assessments fall with the market. The provisional `TAXAMT` aging is only right for the first group.
- **Solution (Solved):** age values by county × type × tier (`scripts/value_factors.py`, `add_aged_values`). Zillow gives type and tier as separate series, so factor = type growth × tier growth ÷ middle-tier growth.

### Zillow vs FHFA vs actual sales
- **Finding (2024 avg → Q4 2025, single-family, 25 FL metro areas):** Zillow and FHFA rank areas the same (correlation 0.84), but Zillow shows ~4.7 points more decline (weighted: Zillow −5.6%, FHFA −0.8%). Gap is larger where FHFA only has its all-transactions index (−6.1 pts) than purchase-only (−4.2 pts).
- **Tiebreaker (roll's own sales):** median qualified single-family price per sq ft, Jan–Jun 2026 vs Jan–Jun 2025, 38 counties: actual −1.0%, Zillow −3.7%; in the 19 big-metro counties with all three: actual −1.9%, Zillow −4.2%, FHFA 0.0%. Truth lies between — Zillow overstates the decline by ~2–3 points a year; FHFA understates it by ~2.
- **Why they differ:** FHFA is repeat sales on Fannie/Freddie mortgages, so it misses cash buyers (large in Florida) and jumbo loans, and its all-transactions index includes refinance appraisals. Zillow is a model of all homes and can lag or overshoot. Price per sq ft from sales has its own mix effects.
- **Solution (Solved):** keep Zillow for the pattern (county, type, tier) and correct its level with Florida's own sales (`zillow_bias` in `scripts/value_factors.py`): for Jan–Jun 2025 vs Jan–Jun 2026, compare the change in median **sale price ÷ the same parcel's Jan 2026 just value** with Zillow's change; shrink each county toward the statewide figure (weight n/(n+300)); apply over the 1.46-year aging span. Median single-family factor −3.8% → −1.2%; condo −9.7% → −7.2%. Corrected figures fall between Zillow and FHFA in almost every county.
- **Lesson:** median price per sq ft was tried first and failed badly (Hillsborough flipped from −5% to +8%, Charlotte −16% to +1%), because 2026 sales were full of new homes and 2025 sales included hurricane-damaged homes. A sale-to-appraisal ratio holds the property fixed. Exclude new construction too.
- **Assumption:** the bias measured for 2025→2026 also held for 2024→2025. Check with the 2025 roll (by request).

### Just value is ~83% of market value
- **Finding:** January 2026 just value ÷ qualified 2025 sale price has a median of 0.83 (single-family 0.83, condo 0.82, mobile 0.82; 377k sales). Fits the ~15% cost-of-sale adjustment plus lag. PUMS reports market value, so it must be converted before comparing with the roll or applying tax rules.
- **Note:** the NAL only records sales in the roll year and the year before (here 2025 and Jan–Sep 2026). 2024 sales need the 2025 roll (by request).

### PUMS values vs the roll after aging
- **Finding:** with uncorrected Zillow, aged PUMS just value was ~8% below roll homestead medians for single-family and condo. After the sales-based correction it's ~4% below statewide (both types), but still well below in South Florida (single-family: Miami-Dade 0.76, Broward 0.86, Collier 0.85, Palm Beach 0.90) and on target in Hillsborough (0.96) and Duval (0.99). Possible causes: owners' reports, non-homestead owners in PUMS (~1M more owners than homesteads), Zillow's decline vs assessors', or the condo mapping (`BLD` 4–9).
- **Mobile homes:** PUMS has ~518k mobile-home owners; the roll has ~232k homestead mobile-home parcels. Most PUMS mobile homes are on rented lots and aren't real-property parcels, so they can't be compared with (or calibrated to) the roll.
- **Solution (Open):** don't patch values here; the linking/calibration step aligns PUMS values to the roll by PUMA × type × tier. Mobile homes on rented lots need separate treatment.

### Aging reported tax needs each owner's assessment gap
- **Problem:** whether an owner's tax rose by the cap or fell with the market depends on their assessed/just ratio, which PUMS doesn't have. Exemptions are fixed dollar amounts, so taxable value moves faster than assessed value (a +5.7% assessment rise gives +6–7% taxable).
- **Solution (Solved, first version):** estimate the 2024 ratio from move-in year (`MV` midpoint) using Save Our Homes caps vs the Florida price index since purchase (`inputs/fl_soh_history.csv`), roll forward year by year, and apply the homestead exemption separately for school and non-school levies. Statewide median assessed/just 0.63 vs roll 0.66; county pattern weak (correlation 0.40) because it uses a statewide index and ignores portability — refine at linking.
- **BLS API limit:** 25 keyless requests a day; `scripts/fl_soh_history.py` uses FRED for CPI instead. A free BLS key would lift the limit.
- **Computed vs official caps:** computed 2026 cap 2.6% vs official 2.7% (October 2025 CPI missing); official caps override where known.

### Getting the parcel tax roll (NAL files)
- **Source:** Florida DOR Data Portal → Tax Roll Data Files → NAL. One zip per county (67 counties).
- **Roll stages:** preliminary (`2026P`, ~July) and final (`2026F`, certified county by county from October). Each county appears in only one folder — when its final roll is certified, it moves from `2026P` to `2026F`. On 2026-10-13: 29 final, 38 preliminary.
- **Only the current year is public.** Prior years (2002 on) are by request: PTOTechnology@floridarevenue.com.
- **Size:** large counties are 30–60 MB zipped (Miami-Dade 59 MB, Broward 50 MB, Duval 30 MB); small ones ~1 MB.
- **Field layout:** check the current year's NAL user guide; field numbers change between years. Homestead just/assessed values are separate fields; school and non-school assessed values (`AV_SD`, `AV_NSD`) can differ.
- **Storage:** raw files are ~1 GB zipped for the state. Process one county at a time: keep only needed columns and residential parcels, save as Parquet, delete the raw zip (re-downloadable by script).
- **Personal data:** keep parcel ID and property (site) address/location; turn the owner's mailing address into flags (owner's state, out of state, mailing ZIP differs, business, trust) and drop the full address and names.
- **Linking parcels by owner (e.g. homes per landlord):** each owner name becomes an anonymous `owner_id`, a keyed hash (HMAC-SHA256) of the normalized name. A plain hash isn't enough, because names are public in the roll and could be hashed to reverse it. The key is created once in `data/.owner_id_salt` (git-ignored). Replicators generate their own key, so IDs differ between installs but are consistent within one. Matching is only as good as name spelling ("SMITH JOHN" vs "SMITH JOHN A" are different owners); it works best for LLCs and corporations.
- **Timing gap with PUMS:** the public roll is 2026 (values as of Jan 1, 2026); PUMS is 2024. Age PUMS to 2026 before comparing.
- **Owner ZIP often blank:** Miami-Dade leaves `OWN_ZIPCD` blank on 72% of parcels. `own_zip_differs` is therefore NA (unknown) when either ZIP is missing, not False. The checks file reports the missing share per county.
- **Unreliable server:** downloads stall or reset mid-file (Miami-Dade failed twice). `scripts/fl_parcels.py` uses curl with resume and retries until the zip verifies.
- **County list:** file names are inconsistent (e.g. Broward has no county number). The list is saved by hand in `manifests/fl_nal_2026.csv`; refresh it as counties move from preliminary to final.
- **Directory pages load with JavaScript**, so scripted listing needs a browser or the direct file URLs: `https://floridarevenue.com/property/dataportal/Documents/PTO Data Portal/Tax Roll Data Files/NAL/<stage>/<file>.zip`.

---

## Ohio

### Rollback base year undefined
- **Problem:** Ramaswamy's "pre-pandemic" rollback has no specified year; analyses have used 2020 or 2021.
- **Solution (Planned):** rollback year is a setting (2019 / 2020 / 2021), separate from the 2026 base year; report sensitivity.

### HB 920 reduction factors
- **Problem:** most voted levies raise a fixed dollar amount; when values rise, effective rates fall automatically. Tax isn't simply value × rate, and a rollback interacts with this.
- **Solution (Open):** confirm current rules (including inside-millage limits) before building the Ohio module.

### Parcel data is county-level
- **Problem:** no single statewide parcel file, which complicates top-code Method B.
- **Solution (Open):** use Method A or collect county files.

---

## Texas

### Parcel data is county-level (appraisal districts)
- **Problem:** as in Ohio.
- **Solution (Open):** use Method A or collect files from the largest appraisal districts.

### Existing homestead cap
- **Problem:** Texas already caps annual growth in homestead assessed value (10%), creating an assessed/market gap like Florida's.
- **Solution (Open):** verify current law; reuse the Florida cap logic.
