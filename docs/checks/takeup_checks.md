# Check: take-up of bigger homestead exemptions (2026-10-23)

`scripts/check_takeup.py`

## 1. Florida 2006-2009 homestead-exempt parcels

| Year | Parcels | Change |
|---|---|---|
| 2006 | 3,938,377 |  |
| 2007 | 4,027,235 | +2.26% |
| 2008 | 4,047,408 | +0.50% |
| 2009 | 4,017,811 | -0.73% |

(57 of 67 counties parsed; the Data Book's own statewide totals row: 2006 4,385,075, 2007 4,484,431, 2008 4,506,860, 2009 4,474,295.)

Counties parsed: 57 of 67 (Miami-Dade is listed as Dade); missing: Charlotte, Hillsborough, Indian River, Jackson, Jefferson, Lafayette, Leon, Wakulla, Walton, Washington.
Across counties, growth in 2007 +2.65% (sd 1.81%), 2008 +1.53% (sd 1.81%), 2009 +0.08% (sd 1.38%).

Placebo, 2009 against 2008 (no new exemption that year): slope -0.10 points of growth per $100 of the same gain measure (correlation -0.04).

Same, controlling for the change in growth of all parcels in the county: slope +1.66 points of growth per $100 of gain (se 0.40); the control's coefficient +0.11.

Dose-response across 54 counties: change in homestead-count growth from 2007 to 2008 against the gain from $25,000 more exemption (county operating millage x $25,000; mean $157, range $67-$250): slope +1.74 points of growth per $100 of gain (se 0.39), correlation +0.53.

Model rule (20% at $2,500): a $300 gain gives 2.6% of non-claimers; with 0.7-1.0 million non-claimers that is 0.46%-0.66% of homestead parcels, spread over two years. The county-to-county spread in annual growth (sd 1.8%) and the statewide swings (2007 +2.3%, 2008 +0.5%, 2009 -0.7%, the housing crash) are many times larger, so 2008 can neither support nor reject the rule.

## 2. Texas homestead counts by school district

Count = value lost to the previous increase step / step size. Statewide totals should reproduce the research note (5.756M, 5.947M, 6.151M):

| Year | Homesteads | Change |
|---|---|---|
| 2022 | 5,756,352 |  |
| 2023 | 5,946,590 | +3.30% |
| 2024 | 6,150,390 | +3.43% |

752 districts with at least 500 homesteads: growth 2023 to 2024 median +2.52% (interquartile +1.00% to +4.75%); 2022 to 2023 median +2.53%. Correlation of the two growth rates across districts +0.46.

Excess claims in 2024 over a trend, and the share of non-claiming owner units they imply (non-claiming = ACS owner units minus claims):

| Trend growth assumed | Excess claims | Non-claiming owner units 2023 | Share of non-claimers | Implied share at $2,500 (gain $681 now) |
|---|---|---|---|---|
| owner-unit growth 2024 (1.2%) | 130,815 | 1,101,779 | 11.9% | 37% |
| homestead growth 2019-21 (1.7%) | 102,708 | 1,101,779 | 9.3% | 30% |
| 2023 growth repeated (3.3%) | 7,275 | 1,101,779 | 0.7% | 2% |

The research note used 4-5.5% of non-claimers at a $600-680 gain, which gives 16-21% at $2,500. Excess claims of about 2 points of growth (100-130k units) are 9-12% of the roughly 1.1 million non-claiming owner units under the first two trends. Caveats: growth in 2022-23 (5.3%, 3.3%) was above trend too, partly SB 8 (claiming in the year of purchase) and the 2022 increase, so 2024 may include delayed response to those; some owner units can't claim (rented lots, entities); Texas needs an application.

## Reading (2026-10-23)
- **Texas (statewide counts reproduce the research note exactly).** The note's step from "about 2 points above trend, ~120k claims"
  to "4-5.5% of non-claimers" is an arithmetic slip: 100-130k claims out of ~1.1 million non-claiming owner units is 9-12%, which
  would put the Florida central take-up near 30-37% at a $2,500 gain, not 20%. But the excess depends entirely on the trend:
  against 2023's own growth (3.3%) there is no excess (0.7%, 2% at $2,500). Texas growth was 5.3%, 3.3%, 3.4% in 2022-24, against
  1.5-1.9% in 2019-21, so the reasonable range of the excess spans nearly everything from 0 to a third of non-claimers. The 10-40%
  low-high range the page shows covers it; the 20% centre is a judgement, not a measurement.
- **Florida 2008.** Homestead-exempt parcels (Data Book totals): 4.385M, 4.484M (+2.3%), 4.507M (+0.5%), 4.474M (-0.7%). Across
  54 counties the change in growth from 2007 to 2008 rises with the size of the new exemption's gain (+1.7 points of growth per $100
  of county-levy gain, se 0.4, also with a control for all-parcel growth), and the same regression for 2009 shows nothing (-0.1).
  Read at face value that is a response several times the model's. But low-millage counties are the high-value coastal and southern
  counties that the housing crash reached first, so a regional crash timing can look the same. Not a clean test either way.
- So neither check validates 20%. Texas supports a range from ~0 to ~35%; Florida 2008 is suggestive of a visible response,
  confounded by the crash. The first-order fix is documentary: describe the setting as a judgement inside a 10-40% range.
  Whether to move the centre up (30% is the better-supported single number from Texas' 2024 excess) is Daniel's call.
