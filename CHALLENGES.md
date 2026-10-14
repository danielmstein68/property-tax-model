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
- **Solution:** give each top-coded home its own value.
  - **Method B (Solved for Florida, `ptm/topcode.py`):** with a full parcel roll, skip curve-fitting and draw from the roll's actual top homesteads. Cut-off is statewide (PUMS top-codes above one state amount): the value of the N-th most valuable roll homestead, N = weighted top-coded households. Each region (county with ≥ 20 top-coded records and ≥ 30 roll homes above the cut-off; the rest pooled) uses its own roll homes above the cut-off. Households are matched by reported tax (higher tax → more expensive home, with noise) via weighted quantile mapping, so the region's value distribution is reproduced exactly.
  - **Method A (fallback, when no usable parcel data):** fit a Pareto tail to PUMS homes just below the cut-off, constrained so the draws average the top-coded amount (the roll supports that amount being the mean above the cut-off). Validate against any published totals available.
- **Don't take "the top N parcels" per region:** in counties with few expensive homes that reaches below the statewide cut-off (Brevard's top N started at $1.5M). Draw only from homes above the cut-off; count mismatches between PUMS and the roll (Brevard 2,088 top-coded vs 252 roll homes above $3.09M; Collier 3,723 vs 7,174) are sampling noise / over-reporting for value calibration, not for top-coding.
- **Detection:** top-coded records are the ties at the column maximum (`flag_topcode_valp`, `flag_topcode_taxamt`).

### Top-coded income
- **Problem:** household income (`HINCP`) isn't top-coded itself; its components (wages, investment income, ...) are top-coded per person. So the tie-at-max test doesn't work for income.
- **Solution (Open):** either drop the income flag and note the limitation, or detect component top-codes in the person file.

### Owners reporting $0 property tax
- **Problem:** some owners report $0 tax. It may be real (exemptions) or misreporting (escrow payers who don't know).
- **Finding:** in the roll, 3.9% of homesteads have $0 taxable value — 155,764 of 201,438 because of the **disabled veterans' total exemption**, then cheap homes (31k), veterans' discount (9k), totally disabled (5k). PUMS homesteads report $0 at 4.3%, nearly the same, so most zeros are real; the ~150k unexplained zeros on homes over $200k were mostly veterans. Excess PUMS zeros sit in $50–200k homes.
- **Solution (Solved):** `assign_exemptions` gives homesteads the special exemptions, matching roll counts by county group, then classifies $0 owners as total exemption / cheap home / misreported (69k, modelled tax at calibration).
- **Lesson:** PUMS's veterans' disability band (70–100%) is broader than the requirement (100% permanent and total) and misses surviving spouses; choosing by it alone gave the exemption to households that mostly pay tax (18% reported $0). Reported $0 as the main evidence, with veteran/widowed signals as tie-breakers, raised that to 92%.
- **Exemption codes:** DOR's NAL user guide is a PDF; `pypdf` extracts the code table. Codes saved in `inputs/fl_exemption_codes.csv`.
- **Double counting:** counting exemption codes separately double-counts homes with both county and city versions (e.g. senior 03 + 04). Count the union per parcel.

### No homestead / primary residence flag
- **Problem:** PUMS doesn't say whether an owner claims a homestead exemption. Florida: 6.35M PUMS owner households (2026 weights) vs 5.21M homestead parcels — ~1.1M owners don't claim.
- **Why (roll evidence):** of 3.05M non-homestead single-family/condo/co-op/mobile parcels, 1.39M have out-of-state owners, 348k Florida businesses (LLCs can't claim), 434k Florida individuals mailing to a different ZIP, **719k Florida individuals mailing to the same ZIP** (likely owner-occupied non-claimers), 152k unknown ZIP. Reasons: mobile homes on rented lots (~290k; not real property); snowbirds counted as Florida households by the ACS 2-month residence rule but homesteaded elsewhere; non-permanent residents (ineligible); LLC/corporate title; recent buyers not yet filed; never applied.
- **All reasons someone may not claim:**
  - *Not eligible:* primary home elsewhere (snowbirds, second homes); spouse claims elsewhere (one per couple); not a permanent resident; didn't own or live there on Jan 1; title in an LLC/corporation/partnership or a non-qualifying trust; title holder lives elsewhere (partial exemption for co-owners); mobile home on a rented lot; homestead removed (renting it out, ineligibility finding).
  - *Eligible but didn't file:* missed the March 1 deadline; unaware or confused (new to Florida, language); keeping residency elsewhere on purpose; moved within Florida and didn't re-file. **These would file more if the exemption grew** (take-up response).
  - *Measurement, not real non-claimers:* ACS 2-month residence rule counts seasonal residents; tenure misreporting; survey vs roll timing; parcel vs household type (duplex/small-building owners homestead on multi-family parcels; co-ops recorded separately).
- **Solution (Solved):** mobile homes first (`assign_mobile_home_lots`); then `assign_homestead` matches roll homestead counts by PUMA × home type, counting multi-family (003, 008) and co-op (005) homesteads as "condo" — otherwise duplex owners would look like non-claimers. Households are chosen mainly by an **implied-rate test**: reported tax too high to be a homestead compared with similar-tenure neighbours in the PUMA. Demographic signals alone (non-citizen, snowbird profile, recent mover) changed who was picked but left their tax per dollar identical to homesteads (1.00×); the implied rate gives 2.06×, matching the roll (~2×). Comparing with all owners in the PUMA instead of similar-tenure ones over-picked long-time owners, because the estimated Save Our Homes gap is too deep for them.
- **Lesson:** when choosing which households get a tax-relevant label, use reported tax as evidence first; demographics second.

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
- **Solution (Solved):** Method B using the Florida DOR parcel tax roll (see above). Results (2024 market value): statewide cut-off **$3,088,769**; 12 regions (11 counties + rest of Florida); imputed weighted mean $5.94M (regional tail means $3.9M in Brevard to $8.2M in Palm Beach; maximum $263M); weighted total $314B vs PUMS $342B (−8%, because PUMS over-represents top-codes in cheaper regions); reported-tax/value rank correlation 0.59–0.83 by region.
- **Finding (statewide):** the top 52,868 roll homesteads (= PUMS weighted top-codes) start at ~$3.0M and average $6.29M vs the $6.47M replacement amount — same as Miami-Dade.
- **Top-coded tax ($42,500):** not imputed yet; needs county tax rates (piece 7). Top-coded owners' reported tax is 0.69% of imputed just value vs ~0.9–1.15% implied by the roll's taxable values — partly the $42,500 floor, partly low tax rates in wealthy areas.
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
- **Solution (Solved):** after homestead status, quantile-map homesteads onto roll homestead just values by county group × home type (`calibrate_values`); non-claimers take the homesteads' ratio at the same value position. Matching percentiles keeps weights (already matched to counts) and each household's rank; only levels move. County groups (counties sharing PUMAs merged, 41 groups) make PUMS and roll areas line up exactly. Mobile homes on rented lots are excluded (piece 2).

### Aging reported tax needs each owner's assessment gap
- **Problem:** whether an owner's tax rose by the cap or fell with the market depends on their assessed/just ratio, which PUMS doesn't have. Exemptions are fixed dollar amounts, so taxable value moves faster than assessed value (a +5.7% assessment rise gives +6–7% taxable).
- **Solution (Solved, first version):** estimate the 2024 ratio from move-in year (`MV` midpoint) using Save Our Homes caps vs the Florida price index since purchase (`inputs/fl_soh_history.csv`), roll forward year by year, and apply the homestead exemption separately for school and non-school levies. Statewide median assessed/just 0.63 vs roll 0.66; county pattern weak (correlation 0.40) because it uses a statewide index and ignores portability.
- **Solution (Solved, 2026 gaps from the roll):** `assign_assessment_gaps` gives each owner the actual school/non-school ratios of a roll donor in the same county group × type × value third × homestead status, handing out donors in order of a 50/50 blend of the move-in estimate and the gap implied by reported tax. Area pattern now matches the roll exactly; recent buyers stay at 1.0; fit to reported tax improves (spread 0.80 → 0.57).
- **Lesson (again):** ordering by move-in category alone made gaps random within each category and fit reported tax *worse*; adding reported tax as evidence fixed it. Going tax-only overfit (recent buyers got 0.71) — keep known structure (recent buyers have no gap) alongside the tax evidence.
- **BLS API limit:** 25 keyless requests a day; `scripts/fl_soh_history.py` uses FRED for CPI instead. A free BLS key would lift the limit.
- **Computed vs official caps:** computed 2026 cap 2.6% vs official 2.7% (October 2025 CPI missing); official caps override where known.

### Simulating how rates are set (2026)
- **Data:** DOR Data Book has 2026 *preliminary* county all-property taxable value, new construction and school taxable value (scripts/fl_databook.py, dated folders since the "current year" files are overwritten). FLDOE's 2026-27 FEFP Second Calculation gives official RLE school millage for all 67 districts (fldoe.org blocks scripts; origin.fldoe.org works).
- **Rolled-back rate** = last year's levy / (taxable - new construction): 2025 vs DOR official, median error -0.10%; 2026 vs 14 official/reported, median 0.55% (misses from annexations/deletions not in the data book).
- **2026 law change:** majority vote now capped at the rolled-back rate; 110% needs two-thirds; above needs unanimous (s. 200.065(5)(a), ch. 2026-239/240). Visible in 2026: Pasco and Volusia adopted exactly rolled-back; Brevard exactly 110%; Franklin 12.7% above (unanimous).
- **Behaviour:** of 22 final county rates, 13 kept last year's rate, 7 cut (3 to exactly rolled-back), 2 raised. "Keep last year's rate" predicts best; small counties raised more often.
- **Collecting adopted rates is slow:** no statewide source until DOR's 2026 Table 1; county resolutions are scattered, many sites block scripts, news often reports combined or tentative rates. Watch for definitions: Table 1's county line may be a countywide total (Orange, Charlotte, Nassau, Hillsborough incl. debt), not the general fund alone. Table 1 PDF reading for Manatee gives 0.4833 vs the county's 6.0326 countywide rate — re-check.
- **Search budget:** subagents share a per-session web-search limit (200); fan-outs can exhaust it.

### Tax rates: what's published
- **Tax district rate tables (TACD):** one file per county mapping each tax district code (`TAX_AUTH_CD`, on every parcel) to its millage by component. Latest is **2025**; 2026 isn't posted until after rates are adopted (September) — expect early the following year. Layouts differ by county, so parsing needs care.
- **The web listing hides spreadsheets.** The DOR portal page only lists PDFs; 8 counties' 2025 TACDs are `.xls`/`.xlsx` (Baker, Brevard, Broward, Gadsden, Hernando, Lee, Palm Beach, Sarasota) and Orange has an extra `Orange County City TACD.XLSX` (a broken cross-join — every code carries every levy; don't use for composition). List a folder's real contents with SharePoint REST: `https://floridarevenue.com/property/dataportal/_api/web/GetFolderByServerRelativeUrl('<folder path>')/Files`. Only **Liberty** genuinely has no 2025 TACD. (We first believed nine counties were missing and sourced them from appraisers — those values should be checked against the DOR spreadsheets.)
- **Comparison of levies (Table 1):** every county plus statewide: each authority's millage, rolled-back rate, taxes levied. One file name has a DOR typo ("Heranando").
- `scripts/fl_rates.py` downloads both from `manifests/fl_rates_2025.csv` (URL paths contain spaces — encode the whole URL).
- **Table 1 covers county and city governments only** — no school boards or independent special districts. School millage comes from FLDOE's 2025-26 district budget summaries (fldoe.org returns 403 to scripts; fetched through a browser).
- **Reading the tables (Solved, with helpers):** a generic line reader passed in only ~half the counties and was often silently wrong (e.g. Miami-Dade unincorporated 24.32 vs correct 16.93 mills for 221k homesteads), so every county was read individually and checked: components re-added to the printed total, county/city rates vs Table 1, total ≥ school + county general, city minus unincorporated ≈ city millage, school vs FLDOE. Seven counties are scans (transcribed from page images); Orange lists rates by authority, not district, so its district totals are reconstructed (partly from outside knowledge — replace with the Orange appraiser's table); Pasco's table carried stale 2024 county/city/school rates (corrected to Table 1 and FLDOE). Per-county notes: `inputs/fl_district_rates_2025/notes/`.
- **The nine missing counties:** Broward, Lee, Brevard, Baker, Hernando from appraiser/tax collector tables; Palm Beach's 2025 table recovered from the Internet Archive (it matched a rebuild from 2026 composition × 2025 rates exactly); Sarasota rebuilt from 2026 composition × 2025 certified rates (no 2025 copy archived); Gadsden and Liberty built from county, city, school and water district rates. Broward's letter-suffix codes (18% of its homesteads) lack a key to their special districts, so they miss 0.01–2 mills.
- **Lesson:** a parser that "mostly works" is dangerous for rates — errors look plausible. Check each county against independent totals before use.
- **Update:** the "nine missing" were mostly hidden DOR spreadsheets (see above). Orange's reconstruction was wrong for 31 of 81 codes (up to 3 mills) — replaced with the Orange Property Appraiser's official 2025 FINAL totals (read with `pdftotext -table`; plain text extraction interleaves its three columns). Broward and Lee now from DOR spreadsheets. Lesson: reconstruction from outside knowledge is a last resort — keep looking for the official file.
- **DOR file-name typos:** "Heranando Table 1.pdf", "Madision Table 2.pdf" — normalized in the manifest.
- **Validating taxable values with official levies:** Table 1 (each county government's levy) × Table 2 (share levied on homestead property) gives official homestead county taxes; the county rate is countywide, so comparing with modelled homestead taxable × rate tests values, gaps and exemptions without depending on district assignment. Duval can't be checked this way (consolidated city-county with three general-government levies).
- **Reported tax isn't a calibration target:** modelled homestead county taxes match official levies within ~5% (the expected 2025-levy vs 2026-value gap), but PUMS-reported tax differs from modelled tax by county in a regional pattern (South Florida reports less; Polk, Brevard, Lee more) that flat fees per parcel don't explain (correlation −0.09). Decision: baseline tax = rules × official rates; reported tax is only evidence for imputation. Calibrating to reported tax would import survey reporting error.
- **City vs unincorporated for each district:** parcels' mailing city is unreliable (unincorporated Orange "ORG37" parcels use Orlando addresses; Hillsborough's unincorporated MSTU ≈ Tampa's city rate). Use district names from the rate tables first ("Unincorporated", "City of Tampa"); fall back to mailing city only if total − school − city ≥ the county government's rate (every district pays it).

### Testing the rules engine against the roll
- **Method:** `scripts/roll_test.py` feeds each residential parcel's own assessed values and recorded exemptions to the engine and compares taxable value with the roll's TV_SD (school) and TV_NSD (county). Result: 99.39% exact on all 9.85M parcels; 99.82% excluding explained cases.
- **Rules the roll revealed (now in the engine):**
  - Homestead exemptions apply only to the **homestead part** of a parcel (owner's unit in a duplex, the home on a mixed lot): measured on `AV_HMSTD`, not the whole parcel.
  - **Co-owners** who don't live there reduce the exemption proportionally (e.g. $12,500 = half).
  - **Save Our Homes status ≠ exemption granted:** contiguous land can be assessed as homestead while the exemption sits on the house's parcel. Use the exemption fields, not `JV_HMSTD`, to tell who gets the exemption.
  - The **veterans' discount** is a percentage applied per levy (the roll records the county dollar amount).
- **County data quirks:**
  - **Brevard records the $5,000 disability exemption under code 08** (statewide: total disability exemption). Treat 08 as total only when it wipes out the value. This also inflates statewide counts of the total disability exemption (~8,700 of 14,967).
  - **Gadsden's preliminary 2026 roll uses the 2025 second-band amount** ($25,722 instead of $26,411; 4,712 parcels off by $689). Recheck with the final roll.
  - **Broward condo common elements** (use 009) carry a nominal $10 value and $0 taxable; not homes.
- **Out of scope:** 28k parcels carry exemptions the spec doesn't cover (charitable, affordable housing, etc.).
- **Assessment rules, partly testable without a prior-year roll:** homes sold in 2025 must be reset to just value on the 2026 roll. Non-homesteads: 100% (school) and 99.8% (non-school) are. Homesteads: 74.7% are; for 99.8% of the rest, just − assessed equals the recorded **portability** amount (`ASS_DIF_TRNS`) exactly. So ~25% of 2025 homestead buyers ported Save Our Homes savings (median $104,957; 1.9% at the $500k cap) — needed when projecting movers. `ASS_TRNSFR_FG` is filled on every parcel, so use `ASS_DIF_TRNS > 0` to identify portability.

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

### Validating the 2026 status quo (2026-10-14)
- **Problem:** how close is the modelled 2026 tax to independent numbers? Script: `scripts/validate_2026.py`.
- **Against the parcel rolls** (homestead parcels, 2025 district rates on both sides): tax $20.79B vs roll $21.10B (−1.5%); average $4,035 vs $4,056; median $2,750 vs $2,739; county totals correlate 0.999; large counties within ~4%. Partly by construction (homestead counts, just values, assessed/just ratios and districts are all drawn from the roll), so this mainly tests the exemption and cap engine. Small counties (< ~100 PUMS records) are noisy. Monroe was off (−31%) — fixed, see next entry. The $2M-and-over band is 11% low after the change below (was 4% low).
- **Against reported tax** (ACS `TAXAMT` aged to 2026): model $25.17B vs reported $26.22B (−4%; some owners include non-ad valorem fees). By income decile the model is 4–11% below reported except the top decile (+3%).
- **Finding:** by years in home, the model was 23% below reported for owners there 20+ years and 17% above for recent buyers. Assessed/just ratios from roll donors were ordered by a 50/50 blend of the move-in-year estimate and the ratio implied by reported tax, which made long-time owners' gaps too deep. Recent buyers' reported tax implies a ratio of 0.68, which is implausible right after a reset — many report the previous owner's capped bill — so reported tax is a poor guide for them.
- **Solution (Solved):** `assign_assessment_gaps(tax_weight=1.0, recent_tax_weight=0.2)`: owners in the home 5+ years are ordered by the reported-tax ratio; recent movers (MV 1–3) mostly by move-in year. Model ÷ reported by years in home went from 1.17 / 1.06 / 1.01 / 0.84 / 0.77 to 1.24 / 0.98 / 0.91 / 0.87 / 0.88; income-decile ratios moved ≤ 1 point; owners within 25% of their reported tax rose from 49% to 55%. Effective rate on value: recent buyers 1.10%, 20+ years 0.63% (was 1.04% / 0.54%). Variants tested (0.5; 0.8/0.2; 1.0/0.2; 0.8/0.5) are recorded in this entry's numbers.

### Monroe pooled with Miami-Dade (2026-10-14)
- **Problem:** PUMA 08625 covers all of Monroe plus 10 Miami-Dade tracts, so `county_groups` merged the two counties into one area. Monroe owners were calibrated to Miami-Dade's values and assessment gaps: model homestead just value $0.95M vs roll $1.20M, assessed/just 0.48 vs 0.60, average tax $3,360 vs $5,431 (−31%). St. Johns was merged with Putnam the same way.
- **Solution (Solved):** a county with a PUMA entirely its own (Miami-Dade, St. Johns) is no longer merged through a PUMA it shares; the shared PUMA goes to the small county's area, and the big county's parcels in those tracts are assigned by tract (`ptm.geo.parcel_area`, used in value calibration, assessment gaps, exemption counts and city senior exemptions). A looser rule (any county with 2+ PUMAs) would also have split Highlands, whose PUMAs are all shared, leaving it no PUMS households — rejected. Result: Monroe 0.95 of roll (was 0.69), Miami-Dade 0.99 (was 1.03), St. Johns 1.00; statewide unchanged ($25.15B owner tax).
- **Leftover:** 44% of Miami-Dade parcels have no usable tract code (`CENSUS_BK`), so some Dade parcels in the shared tracts stay in Miami-Dade's area. Putnam remains high (1.21, 218 records).

### $2M+ homesteads taxed too low (2026-10-14)
- **Problem:** after ordering gaps by reported tax, $2M+ homesteads came out 11% below the roll (assessed/just 0.54 vs roll 0.64). High-value owners whose tax isn't top-coded report low tax relative to their calibrated value ($13,250 reported vs $18,290 modelled), so ranking the tax-implied gap across a whole donor cell (top third of an area's values also holds $600k homes) partly sorted by value and gave them the deepest gaps.
- **Solution (Solved):** rank the tax-implied gap only within value tenths of each donor cell (`assign_assessment_gaps(tax_rank_value_groups=10)`). Tested none / fifths / tenths. With tenths: $2M+ 0.94 of roll (was 0.89), $1–2M 1.02, assessed/just 0.61; homestead average $4,069 vs roll $4,056; years-in-home vs reported 1.22 / 0.96 / 0.93 / 0.90 / 0.90; Monroe 1.01, Putnam 1.12 (was 1.21). Trade-offs: homes under $100k now 0.91 of roll (avg bill ~$300; < 0.3% of tax); owners within 25% of their reported tax 53% (was 55%).

### 2026 city rates; Palm Beach had no city levies (2026-10-14)
- **Collected:** `scripts/fl_city_rates_2026.py` → `inputs/fl_city_millage_2026.csv` (91 cities). County property appraiser sheets list every city's 2025 and 2026 rate (Miami-Dade, Palm Beach proposed; Manatee final; Lee preliminary book), plus hand-collected city votes with URLs. Applied in `ratemodel.apply_2026_rates` as (2026 − 2025) on `millage_municipal`. Net effect +$21M (Jupiter +$10.5M, Palmetto Bay +$2.4M, Delray Beach +$2.2M; Davie −$2.0M).
- **Problem found:** Palm Beach's DOR Table 1 lists cities by bare name ("Boca Raton"), and `district_classes` only recognised "City/Town/Village of", so no Palm Beach district had a city: city levies were counted as county (totals right, split wrong).
- **Solution (Solved):** accept bare-name Table 1 authorities that aren't county/school/special-district levies (`NOT_A_CITY`), and let a district note that is just a city's name select that city. Palm Beach: 78 of 127 districts now have a city (55% of owners); 13 districts elsewhere gained their city (e.g. LaCrosse, Callaway, Fort Walton Beach). Statewide municipal tax $2.85B → $3.32B (moved from "county"; total unchanged apart from 2026 city rates).
- **Open:** mailing-city matches put unincorporated owners in Bradenton and Naples (see LIMITATIONS); Intercession City (Osceola) likely a special district.

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
