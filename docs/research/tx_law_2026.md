# Texas property tax law for tax year 2026 (owner-occupied homes)

Research notes for the Texas model, gathered 2026-10-20. Written in the style of `inputs/fl_law.yaml`:
each rule has its citation, a short quote, a source URL and a confidence level. This is a research
file, not the model's rules spec. A `tx_law.yaml` should be built from it.

**Sources.** Statute text comes from the Texas Legislature's statutes site. The chapter files were
downloaded on 2026-10-20 from `tcss.legis.texas.gov/resources/TX/htm/TX.<ch>.htm`, the data source
behind `statutes.capitol.texas.gov`. Those files include every 89th Legislature amendment (regular
session and the 1st and 2nd called sessions of 2025). The URLs below use the public
`statutes.capitol.texas.gov` form. Quotes are verbatim and kept short.

**Confidence.** high = explicit statute or constitutional text, read in force today; medium = needs
interpretation, comes from an agency letter rather than statute, or is a secondary figure;
low = unverified.

**Law in force vs proposals.** Everything in sections 1-6 is law in force for tax year 2026 unless
it is marked *proposal* or *expired*. The 2025 constitutional amendments were all approved on
Nov 4, 2025 (17 of 17). Bills that failed are listed in section 7.

---

## 0. The 2025 changes that matter for 2026 (summary)

| Change | Bill / amendment | Voter approval | First tax year | Status for 2026 | Confidence |
|---|---|---|---|---|---|
| School general homestead exemption $100,000 → **$140,000** | SB 4 / SJR 2 (Prop 13) | Nov 4, 2025 (79.5% yes) | **2025** (retroactive) | In force | high |
| School over-65/disabled extra exemption $10,000 → **$60,000** | SB 23 / SJR 85 (Prop 11) | Nov 4, 2025 (77.7% yes) | **2025** (retroactive) | In force | high |
| School M&O compression of about 6.8 cents through the state compression percentage | SB 1 (GAA, 2026-27), TEC 48.255 | n/a | 2025 | TY2025 state MCR $0.6322; TY2026 $0.6254 | medium (amounts from TEA letters) |
| Business personal property: $2,500 de minimis → **$125,000 exemption** per location | HB 9 / HJR 1 (Prop 9) | Nov 4, 2025 (65.3% yes) | **2026** | In force | high |
| Total homestead exemption for surviving spouse of a veteran who died of a PACT Act condition | HB 2508 / HJR 133 (Prop 7) | Nov 4, 2025 (86.7% yes) | 2026 | In force (new s. 11.136) | high |
| Temporary prorated exemption for a homestead destroyed by fire | SB 467 / SJR 84 (Prop 10) | Nov 4, 2025 (89.3% yes) | 2026 | In force (new s. 11.351) | high |
| Ceiling (freeze) in the year after first qualifying = lesser of computed ceiling and actual tax | SB 2520 | n/a | 2026 | In force (s. 11.26(a-11)) | high |
| Animal feed held for retail sale exempt | HB 1399 / HJR 99 (Prop 5) | Nov 4, 2025 | 2026 | In force (not residential) | high |
| Border security infrastructure exemption | HB 247 / HJR 34 (Prop 17) | Nov 4, 2025 | 2026 | In force (not residential) | high |
| I&S "current debt" limited to the minimum required payment | SB 1453 | n/a | 2026 | In force | medium |
| Voter-approval rate for cities/counties of 75,000+ cut from 3.5% to 2.5% (House version: 1%) | SB 10, 89th 2nd C.S. | — | — | **Failed. Not law.** s. 26.04(c) still says 1.035 | high |
| Extend or change the 20% circuit breaker (e.g. SB 322: extend to 2031 at 10%) | various 89R bills | — | — | **Not enacted.** s. 23.231(k) still expires Dec 31, 2026 | high |

Proposition numbers and percentages are from Wikipedia's results table (medium). One search summary
paired SJR 85 with Prop 10 instead. The statute amendments themselves (SB 4 and SB 23 in s. 11.13,
"eff. November 4, 2025") are high confidence.

---

## 1. Homestead exemptions

### 1.1 School district general homestead exemption — $140,000
- **Rule:** Every school district exempts $140,000 of the appraised value of a residence homestead.
  Mandatory; applies to M&O and I&S.
- **Parameters:** $15,000 (to 2014); $25,000 (2015-2021); $40,000 (2022); $100,000 (2023-2024);
  **$140,000 (2025 onward, so 2026)**.
- **Citation:** Tax Code s. 11.13(b); Tex. Const. art. VIII, s. 1-b(c); SB 4 s. 1.01 (89R, ch. 338),
  eff. Nov 4, 2025. SJR 2's temporary provision makes the amendment apply from the tax year beginning
  Jan 1, 2025.
- **Quote:** "An adult is entitled to exemption from taxation by a school district of $140,000 of the
  appraised value of the adult's residence homestead" (s. 11.13(b)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.13 ;
  https://statutes.capitol.texas.gov/Docs/CN/htm/CN.8.htm#8.1-b ;
  https://capitol.texas.gov/tlodocs/89R/analysis/html/SJ00002F.htm
- **Confidence:** high.
- **Notes:** State aid holds school districts harmless for the lost M&O and I&S revenue (SB 4;
  TEC ch. 46 and 48). The model's school finance module needs this. The statute applies the
  exemption to "appraised value" (after the 10% cap). The constitution says "market value". Practice
  is appraised value.

### 1.2 School over-65 / disabled additional exemption — $60,000
- **Rule:** On top of 1.1, a homeowner who is 65 or older or disabled gets another $60,000 of school
  exemption. One person can't get both the over-65 and the disabled version from the same unit; they
  pick one (s. 11.13(h)). The exemptions stack: general $140,000 + $60,000 = **$200,000** for an
  eligible senior or disabled owner.
- **Parameters:** $10,000 (2015-2024); **$60,000 (2025 onward)**.
- **Citation:** Tax Code s. 11.13(c), (h), (m)(1) ("disabled" = eligible for Social Security
  disability benefits); Tex. Const. art. VIII, s. 1-b(c); SB 23 s. 1.01 (89R, ch. 340), eff.
  Nov 4, 2025; SJR 85 temporary provision: effective for the 2025 tax year.
- **Quote:** "an adult who is disabled or is 65 or older is entitled to an exemption from taxation by
  a school district of $60,000" (s. 11.13(c)).
- **Quote:** "An eligible disabled person who is 65 or older may not receive both a disabled and an
  elderly residence homestead exemption from the same taxing unit" (s. 11.13(h)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.13 ;
  https://capitol.texas.gov/tlodocs/89R/analysis/html/SB00023F.htm
- **Confidence:** high.
- **Notes:** The over-65 exemption takes effect for the whole year in which the person turns 65
  (s. 11.42(c)). Not prorated.

### 1.3 Local option percentage homestead exemption (any taxing unit) — up to 20%, at least $5,000
- **Rule:** Any taxing unit (county, city, special district, junior college, and also a school
  district) may adopt, before July 1, an exemption of a percentage of the homestead's appraised
  value. The cap is 20%. If the percentage gives less than $5,000, the exemption is $5,000.
  The exemption stacks with all other exemptions.
- **Lock-in:** A school district, city or county that had an (n) exemption for 2022 may not reduce or
  repeal it. This expires Dec 31, 2027 (s. 11.13(n-1)), so the lock binds in 2026.
- **Citation:** Tax Code s. 11.13(n), (n-1); Tex. Const. art. VIII, s. 1-b(e).
- **Quote:** "If the percentage set by the taxing unit produces an exemption ... of less than $5,000
  ... the individual is entitled to an exemption of $5,000" (s. 11.13(n)).
- **Quote:** "The percentage adopted by the taxing unit may not exceed 20 percent." (s. 11.13(n)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.13 ;
  https://comptroller.texas.gov/taxes/property-tax/exemptions/index.php
- **Confidence:** high (rule). Each unit's adopted percentage is data: take it from the roll or
  appraisal district exemption tables.
- **Notes:** Debt pledged before an exemption was adopted can still be levied on the exempt value
  (s. 11.13(i)). Rare, but it exists.

### 1.4 Local option over-65 / disabled exemption (any taxing unit) — at least $3,000
- **Rule:** Any taxing unit may adopt a dollar exemption for over-65 or disabled owners, set by the
  governing body or by petition election. The minimum is $3,000 and there is no statutory maximum.
  Once adopted, it may not be cut below $3,000. A person can't get both the over-65 and the disabled
  version from one unit, but can get them from different units (s. 11.13(h)).
- **Surviving spouse:** A spouse aged 55 or older keeps the deceased spouse's (d) over-65 exemption
  from that unit (s. 11.13(q)).
- **Citation:** Tax Code s. 11.13(d)-(f), (h), (q), (r).
- **Quote:** "The amount ... is $3,000 of the appraised value of the residence homestead unless a
  larger amount is specified" (s. 11.13(e)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.13
- **Confidence:** high (rule). Amounts vary by unit (data).
- **Notes:** School districts may also adopt a (d) exemption. A few do; most don't.

### 1.5 County farm-to-market / flood control exemption — $3,000
- **Rule:** A county that levies the farm-to-market road / flood control tax (Const. art. VIII,
  s. 1-a) exempts $3,000 of homestead value from that tax only. If the county also gives a (d)
  over-65/disabled exemption, the owner takes only the (d) exemption for the FMFC tax; the two are
  not added together (s. 11.13(g)).
- **Citation:** Tax Code s. 11.13(a), (g).
- **Quote:** "entitled to an exemption from taxation for the county purposes authorized in Article
  VIII, Section 1-a ... of $3,000 of the assessed value" (s. 11.13(a)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.13
- **Confidence:** high.
- **Data:** In the Comptroller's 2025 county rates file, 79 counties have an FMFC rate above zero.

### 1.6 Disabled veterans
**(a) Partial exemption by rating (s. 11.22).** This is a dollar exemption of *assessed* value on
one property the veteran chooses (it needn't be a homestead). It applies to every taxing unit.
| Disability rating | Exemption |
|---|---|
| 10% to < 30% | $5,000 |
| 30% to < 50% | $7,500 |
| 50% to < 70% | $10,000 |
| 70% and over | $12,000 |
A veteran aged 65+ with a rating of at least 10%, or totally blind in one or both eyes, or who has
lost the use of a limb, gets $12,000 (s. 11.22(b)). The veteran takes the single highest amount
(s. 11.22(e)(1)). A surviving spouse keeps the amount while unmarried (s. 11.22(c)). A spouse of a
service member who died on active duty gets $5,000 (s. 11.22(d)).
- **Quote:** "A disabled veteran is entitled to an exemption from taxation of a portion of the
  assessed value of a property the veteran owns and designates" (s. 11.22(a)).
- **Confidence:** high. Amounts unchanged since 2009; no 2025 amendment.

**(b) 100% / individual unemployability: total exemption of the homestead (s. 11.131).**
- **Rule:** A veteran with VA 100% disability compensation and a 100% rating (or individual
  unemployability) owes no tax on the homestead. The unremarried surviving spouse keeps the
  exemption, and can carry its dollar amount to a later homestead (s. 11.131(c)-(d)). If the veteran
  qualifies after Jan 1, the exemption is prorated for the rest of the year (s. 11.42(e)).
- **Quote:** "is entitled to an exemption from taxation of the total appraised value of the
  veteran's residence homestead" (s. 11.131(b)).
- **Confidence:** high.

**(c) Donated homestead of a partially disabled veteran (s. 11.132).** The exemption equals the
disability-rating percentage when a charity donated the home at no cost or at 50% or less of
market value. Rare. Confidence high.

- **URL (all):** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.22 ;
  https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.131
- **Stacking:** s. 11.22 can be added to the s. 11.13 homestead exemptions. Under s. 11.131, total
  exemption makes the others irrelevant.

### 1.7 Surviving-spouse total exemptions (homestead, every taxing unit)
| Section | Who | Since | Quote |
|---|---|---|---|
| s. 11.133 | Spouse of a service member killed in the line of duty, not remarried | 2014 | "exemption from taxation of the total appraised value of the surviving spouse's residence homestead" |
| s. 11.134 | Spouse of a first responder killed in the line of duty (an eligible survivor under Gov't Code ch. 615), not remarried | 2016 | same wording; eligibility is "determined by the Employees Retirement System of Texas" |
| **s. 11.136 (new)** | Spouse of a veteran who died of a PACT Act presumptive condition, whatever the rating, not remarried | **2026** (HB 2508, Prop 7) | "regardless of the veteran's disability rating at the time of the veteran's death" |
Each has a portability clause: the dollar amount carries to a later homestead.
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.136
- **Confidence:** high (rules). Take-up counts must come from the roll.

### 1.8 Other homestead-related exemptions (note only)
- **s. 11.351 (new 2026, SB 467 / Prop 10):** a homestead improvement completely destroyed by fire
  and uninhabitable for at least 30 days is exempt for the rest of that tax year, prorated by days
  ("a fraction, the denominator of which is 365"). Confidence high. Too small to model.
- **s. 11.35:** temporary exemption for property damaged in a declared disaster (15-100% by damage
  level). Amended by SB 850 (2025, procedural). Confidence high. Not modelled in the baseline.
- **s. 11.13(k):** the exemption doesn't cover any part of the home used for purposes incompatible
  with living there (e.g. a rented portion).
- **Heir property:** an heir-owner who occupies the home may claim it and counts as the sole owner
  (s. 11.13(h), s. 11.26(p)).

### 1.9 Exemption ordering / stacking (summary for the model)
For each taxing unit: *taxable = appraised value (after the 10% cap) − exemptions that unit gives*.
- **School:** $140,000 + ($60,000 if 65+ or disabled) + local % (n) if adopted + local (d) if
  adopted + DV s. 11.22 amount. Then apply the school tax ceiling (section 3).
- **County:** local % (n) + local (d) over-65/disabled + DV amount; FMFC tax separately ($3,000 or (d),
  not both). Then the county ceiling if adopted.
- **City / junior college:** local % (n) + local (d) + DV amount. Then the ceiling if adopted.
- **Special districts:** local % (n) + local (d) + DV amount. No ceilings.
- The constitution and statute don't set an order for applying these, because they are all dollar
  or percentage amounts of the same appraised value. The (n) percentage is applied to appraised value,
  not to value net of other exemptions (s. 11.13(n): "a percentage of the appraised value").
  **medium.** Check that rolls match.

---

## 2. Appraisal limits

### 2.1 Homestead appraisal cap — 10%
- **Rule:** A homestead's appraised value may rise by at most 10% of last year's appraised value,
  plus the market value of new improvements, and is never above market value. The cap starts on
  Jan 1 of the year *after* the owner first qualifies for the homestead. Under s. 23.23(c-1), a buyer
  who claims in the year of purchase (s. 11.42(f)) counts as qualifying the next Jan 1. The cap ends
  when neither that owner nor the owner's spouse or surviving spouse qualifies. The cap applies to
  every taxing unit.
- **Parameters:** 10% (since 1998). No 2025 change.
- **Citation:** Tax Code s. 23.23(a), (c), (c-1), (e).
- **Quote:** "the sum of: (A) 10 percent of the appraised value of the property for the preceding tax
  year; (B) the appraised value ... for the preceding tax year; and (C) the market value of all new
  improvements" (s. 23.23(a)(2)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.23.htm#23.23 ;
  https://comptroller.texas.gov/taxes/property-tax/valuing-property.php
- **Confidence:** high.
- **Notes:** Rebuilding after a casualty doesn't count as a new improvement unless the home gets
  bigger or better (s. 23.23(f)). The cap is reset on sale (new owner).

### 2.2 Non-homestead "circuit breaker" — 20% (expires after tax year 2026)
- **Rule:** Real property that isn't a homestead (including rentals and second homes) with appraised
  value at or below the threshold in the year it first qualifies may rise by at most 20% a year, plus
  new improvements. It starts on Jan 1 of the year after the owner first owns it on Jan 1 (owners
  before 2023 are treated as owning it on Jan 1, 2023). It ends when ownership changes. Ag/timber
  land and other special-use land are excluded.
- **Threshold:** $5,000,000 (2024); $5,160,000 (2025); **$5,320,000 (2026)**. CPI-U adjusted by the
  Comptroller.
- **Expiry:** "This section expires December 31, 2026." It applies to the **2026** roll. With no new
  law, it is gone for **2027**. No 2025 bill extended it; the statute shows no 89th Legislature
  amendment.
- **Citation:** Tax Code s. 23.231(b)-(d), (f)-(g), (j)-(k); SB 2 (88th 2nd C.S.).
- **Quote:** "20 percent of the appraised value of the property for the preceding tax year"
  (s. 23.231(d)(2)(A)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.23.htm#23.231 ;
  https://comptroller.texas.gov/taxes/property-tax/valuing-property.php (threshold table)
- **Confidence:** high for the rule and expiry. The 2026 threshold, $5,320,000, comes from the
  Comptroller's web table: medium-high.
- **Model relevance:** Rentals and second homes are part of the tax base and revenue, not
  households. The expiry changes the 2027+ projections; non-homestead values jump back toward market.
  It is an open policy question whether the 90th Legislature (Jan 2027) revives it.

---

## 3. Tax ceilings (freezes)

### 3.1 School tax ceiling for over-65 / disabled homesteads (mandatory)
- **Rule:** The school district tax on the homestead of a 65+ or disabled owner can't rise above the
  ceiling. If the owner qualifies after the start of the first year, the ceiling is the *lesser* of
  that year's tax and the next year's (s. 11.26(a), (a-11)). It goes up only for new improvements
  (excluding repairs and code-required work) (s. 11.26(b)). It ends when no qualifying owner still
  lives there. A surviving spouse aged 55+ keeps it (s. 11.26(i)). It carries proportionally to a new
  homestead (s. 11.26(g)).
- **Automatic ceiling reductions (s. 11.26(a-10), from 2024).** Each year the ceiling becomes:
  1. last year's ceiling-limited tax
  2. **minus** last year's taxable value × (last year's MCR − this year's MCR) (*compression
     pass-through*)
  3. **plus** tax on improvements under (b)
  4. **minus** (this year's increase in the s. 11.13(b)+(c) exemptions) × this year's tax rate
     (*exemption pass-through*)
  - For 2025, step 4 passed through the $40,000 + $50,000 = $90,000 increase. For 2026 the
    exemption amounts don't change, so step 4 is $0. Step 2 passes through the TY2025 → TY2026 MCR
    change (state max $0.6322 → $0.6254; each district's own MCRs apply).
- **New for 2026 (SB 2520):** (a-11): for an owner who first qualified partway through last year, the
  ceiling this year is the lesser of the (a-10) amount and the actual uncapped tax.
- **Citation:** Tex. Const. art. VIII, s. 1-b(d); Tax Code s. 11.26 (a), (a-4), (a-10), (a-11), (b),
  (c), (g), (i); SB 2 (88th 2nd C.S.) s. 3.02, 3.15; SB 2520 (89R, eff. Jan 1, 2026).
- **Quote:** "multiplying the taxable value of the homestead in the preceding tax year by a tax rate
  equal to the difference between the school district's maximum compressed rate" (s. 11.26(a-10)(1)).
- **Quote:** "multiplying the amount of any increase ... in the aggregate amount of the exemptions ...
  under Sections 11.13(b) and (c) by the school district's tax rate" (s. 11.26(a-10)(4)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.26 ;
  https://capitol.texas.gov/tlodocs/89R/analysis/html/SB02520F.htm
- **Confidence:** high (text). medium on applying it to the model: (a-10) works from each
  homestead's *prior-year* tax and taxable value, so we need each frozen account's history, or must
  estimate the ceiling from the roll's frozen-tax field.
- **Notes:** Appraisal districts certify the value lost to ceilings for each school district
  (s. 11.26(e)) and the count of frozen homesteads (s. 11.26(e-1)). The Comptroller reports counts by
  Nov 1. These are useful calibration targets.

### 3.2 Local option ceilings — counties, cities, junior colleges
- **Rule:** A county, city or junior college district may adopt a freeze for 65+/disabled homesteads,
  by official action or after a petition by 5% of voters. Once adopted, it can't be repealed (Const.
  s. 1-b(h)). The base year is the first year the person qualified for s. 11.13(c), but not earlier
  than the year the unit adopted the freeze. There is **no** compression or exemption pass-through like
  s. 11.26(a-10). It rises only for improvements. Hospital districts, MUDs and other special
  districts can't adopt one.
- **Citation:** Tex. Const. art. VIII, s. 1-b(h); Tax Code s. 11.261.
- **Quote:** "may not increase the total annual amount of ad valorem taxes ... above the amount of the
  taxes ... imposed on the residence homestead in the first tax year" (s. 11.261(b)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.261
- **Confidence:** high (rule). Which units have adopted it is data (appraisal district tables;
  many large counties and cities have).
- **Note on eligibility:** s. 11.261 is triggered by the *school* s. 11.13(c) over-65/disabled
  exemption, not by a local (d) exemption.

### 3.3 Tax deferral (note only)
- 65+, disabled, and disabled-veteran owners may defer homestead taxes (s. 33.06; amended by HB 851,
  eff. Jan 1, 2026). Deferred taxes are still levied, so this affects cash paid but not levy. Not
  modelled. Confidence high for existence; HB 851's details weren't checked.

---

## 4. Tax rate limits

### 4.1 No-new-revenue (NNR) rate — all units
- **Rule:** The rate that raises last year's levy, less levy lost on property no longer on the roll,
  from this year's value of property that was taxed both years.
  `NNR = (last year's levy − lost property levy) / (current total value − new property value)`.
- **Citation:** Tax Code s. 26.04(c)(1); s. 26.012 definitions.
- **Quote:** "NO-NEW-REVENUE TAX RATE = (LAST YEAR'S LEVY - LOST PROPERTY LEVY) / (CURRENT TOTAL VALUE -
  NEW PROPERTY VALUE)" (s. 26.04(c)(1)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm#26.04
- **Confidence:** high.
- **Note:** A unit other than a school district needs a 60% record vote of its governing body to
  adopt a rate above NNR (s. 26.05(b)).

### 4.2 Voter-approval rate (VAR) — cities, counties, most units
- **Rule:**
  - **Units other than special taxing units:** `VAR = NNR M&O rate × 1.035 + (current debt rate +
    unused increment rate)`
  - **Special taxing units:** `VAR = NNR M&O rate × 1.08 + current debt rate`
- **"Special taxing unit":** a unit (not a school district) whose proposed M&O rate is 2.5 cents or
  less per $100, **or** a junior college district, **or** a hospital district (s. 26.012(19)).
- **Unused increment rate:** up to 3 prior years' unused room under the VAR can be banked
  (s. 26.013). **medium:** check the current text before encoding.
- **Parameters:** 3.5% since tax year 2020 (SB 2, 86th; was 8% "rollback"). **Unchanged for 2026.**
  The 2.5% (Senate) / 1% (House) SB 10 in the 89th 2nd C.S. failed (section 7).
- **Citation:** Tax Code s. 26.04(c)(2); s. 26.012(19).
- **Quote:** "VOTER-APPROVAL TAX RATE = (NO-NEW-REVENUE MAINTENANCE AND OPERATIONS RATE x 1.035) +
  (CURRENT DEBT RATE + UNUSED INCREMENT RATE)" (s. 26.04(c)(2)(B)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm#26.04
- **Confidence:** high.
- **Disaster exception:** in a declared disaster area, a non-school, non-special unit may use the
  8% multiplier plus a disaster relief rate for up to 3 years (s. 26.042; amended by HB 30, 89R,
  eff. Jan 1, 2026, which tightened what counts as a disaster cost). medium.
- **I&S:** SB 1453 (89R, eff. Jan 1, 2026) limits the debt rate to what pays the *minimum* required
  debt service. A higher I&S rate needs a 60% vote and counts as the current debt rate
  (s. 26.05(a-1)-(a-2)). medium.

### 4.3 De minimis rate (small units)
- **Rule:** `De minimis = NNR M&O rate + rate that raises $500,000 + current debt rate`. A unit that
  isn't a special taxing unit, **or** a city under 30,000 population, faces an automatic election
  only if its rate exceeds the *greater* of VAR and the de minimis rate. Between those rates, voters
  may force an election by petition (s. 26.075).
- **Citation:** Tax Code s. 26.012(8-a); s. 26.07(b); s. 26.063; s. 26.075.
- **Quote:** "the rate that, when applied to a taxing unit's current total value, will impose an
  amount of taxes equal to $500,000" (s. 26.012(8-a)(B)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm#26.012
- **Confidence:** high.

### 4.4 Automatic elections — non-school units (s. 26.07)
- **Rule:** If an adopted rate is above VAR (or above the greater of VAR and the de minimis rate for
  units eligible for it), the election is automatic on the November uniform election date. If voters
  reject it, the rate becomes VAR.
- **Quote:** "If the proposition is not approved ... the taxing unit's tax rate for the current tax
  year is the taxing unit's voter-approval tax rate." (s. 26.07(e)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm#26.07
- **Confidence:** high.

### 4.5 MUDs and other Water Code districts (own rules)
- **Low-tax-rate district** (M&O ≤ 2.5¢): election if the tax on the average homestead rises more
  than 8% (Water Code s. 49.23601).
- **Developed district** (95% of build-out financed): automatic election above 1.035 × last year's
  tax on the average homestead, plus unused increment (s. 49.23602).
- **Other (developing) districts:** voters may petition if the tax on the average homestead rises
  more than 8% (s. 49.23603).
- **Quote:** "the rate that would impose 1.035 times the amount of tax imposed by the district in the
  preceding year on a residence homestead appraised at the average appraised value" (s. 49.23602).
- **URL:** https://statutes.capitol.texas.gov/Docs/WA/htm/WA.49.htm#49.23602
- **Confidence:** high (text downloaded the same day).

### 4.6 School districts: MCR, enrichment (golden/copper pennies), I&S, VATRE
- **Tier one / maximum compressed rate (MCR):** each district's MCR is the lesser of:
  - **local compression:** the prior-year MCR, scaled down when the district's value growth exceeds
    2.5% (TEC s. 48.2551(b)(1))
  - **state compression:** the state compression percentage × $1.00 (s. 48.2551(b)(2); s. 48.255)

  A floor keeps any MCR from dropping below 90% of another district's (s. 48.2552). The state
  compression percentage is the lowest of 93%, any lower percentage set in the GAA, and
  PYCP × 1.025/(1+ECPV) (s. 48.255(b)).
  - **TY2025:** state max MCR **$0.6322**; floor $0.5689 (TEA). The GAA (SB 1, 89R) bought about
    6.8 cents of extra compression through the state compression percentage (Senate Research Center,
    SJR 2 analysis).
  - **TY2026:** state max MCR **$0.6254**; floor **$0.5628**; statewide value growth set at 3.60% in
    the GAA. TEA formula: "0.6322 × (1.025 ÷ 1.036) - 0.0000 = $0.6254".
  - **History (low, from memory, not checked against a TEA letter):** $0.6880 (TY2023, after
    SB 2's 10.7¢), $0.6669 (TY2024). Pull the TEA TAA letters for TY2019-2024 before using them.
- **Enrichment (Tier two):** M&O tax above MCR, capped at MCR + $0.17 (TEC s. 45.003(d)).
  - **Golden pennies:** the first 8 cents above MCR (s. 45.0032(b)(1); guaranteed yield at basic
    allotment × 0.02084, s. 48.202(a-1)(1)). Pennies 1-5 need no election; pennies 6-8 need voter
    approval (or a prior authorization).
  - **Copper pennies:** cents 9-17, which need voter approval; guaranteed yield at basic allotment ×
    0.008 (s. 48.202(a-1)(2)).
  - **TY2026 maximum M&O rate:** $0.6254 + $0.17 = **$0.7954**.
- **School voter-approval rate:** `MCR + greater of (last year's enrichment rate, $0.05) + current
  debt rate` (Tax Code s. 26.08(n)). Above that, an automatic voter-approval tax rate election
  (VATRE) is held (s. 26.08(a)). If it fails, the rate can't exceed VAR (s. 26.08(d)). There is no
  3.5% M&O growth multiplier for schools; the MCR value-growth formula does that job.
- **I&S (debt):** no rate cap in statute. New bonds must pass the $0.50 per $100 test in the
  Attorney General's review (TEC s. 45.0031(a)). Bond elections are required (s. 45.003). Since
  2019, ballots must say "THIS IS A PROPERTY TAX INCREASE" (s. 45.003(b-1)).
- **Quote:** "the maintenance tax rate ... may not exceed the rate equal to the sum of $0.17 and the
  district's maximum compressed rate" (TEC s. 45.003(d)).
- **Quote:** "the greater of: (A) the district's enrichment tax rate for the preceding tax year; or
  (B) the rate of $0.05" (Tax Code s. 26.08(n)(2)).
- **URL:** https://statutes.capitol.texas.gov/Docs/ED/htm/ED.48.htm#48.2551 ;
  https://statutes.capitol.texas.gov/Docs/ED/htm/ED.45.htm#45.003 ;
  https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm#26.08 ;
  https://tea.texas.gov/taa-letters/tax-year-2026-maximum-compressed-tax-rates ;
  https://tea.texas.gov/taa-letters/final-maximum-compressed-tax-rates-mcr-and-adoption-tax-rate-tax-year-2026
- **Confidence:** high for statute; high for the TY2026 figures in TEA's letter (Aug 27, 2026 final
  MCR list); medium for the TY2025 compression size and the history.
- **Notes for the school-finance module:** the basic allotment is still $6,160 + GYIA in statute
  (TEC s. 48.051, as amended by HB 2, 89R). HB 2 also repealed the old (c)-(d) subsections and added
  new allotments (teacher pay and others). Tier one funding doesn't depend on compression; compression
  only changes the state/local split (TEA TAA). Districts above their entitlement pay recapture
  (s. 48.257).

---

## 5. Taxing unit types that tax homes, with typical 2025 rates

Calculated from the Comptroller's 2025 Tax Rates and Levies files, unweighted across units (each
unit counted once by taxing-unit ID). The model will use each unit's actual 2026 rate.

| Type | Count with a rate | 5th / 25th / median / 75th / 95th pct total rate per $100 | 2025 levy (Comptroller, statewide) | Rate-limit regime |
|---|---|---|---|---|
| School districts (ISD) | 1,549 rows | 0.667 / 0.819 / 0.960 / 1.090 / 1.241 (M&O median 0.712; I&S median 0.250) | $41.65B (46.6%) | MCR + enrichment + I&S; VATRE |
| Counties | 253 | 0.265 / 0.383 / 0.493 / 0.627 / 0.870 (includes FMFC; 79 counties levy FMFC) | $16.79B (18.8%) | 3.5% VAR |
| Cities | 1,241 | 0.140 / 0.318 / 0.480 / 0.624 / 0.846 | $16.73B (18.7%) | 3.5% VAR; de minimis if under 30,000 |
| Special districts (all) | 2,381 | 0.024 / 0.10 / 0.38 / 0.78 / 1.25 | $14.27B (16.0%) | varies |
| — MUDs | 1,031 | p10 0.25 / median 0.72 / p90 1.25 | | Water Code s. 49.236x |
| — Hospital districts | 133 | 0.069 / 0.212 / 0.449 (p10/med/p90) | | special taxing unit (8%) |
| — Junior colleges | 93 | 0.046 / 0.110 / 0.244 | | special taxing unit (8%); may adopt freeze |
| — Emergency services districts | 383 | 0.030 / 0.090 / 0.100 | | ESD max 10¢ (Health & Safety Code s. 775.0745; not checked) |
| — WCIDs | 154 | 0.038 / 0.370 / 0.950 | | Water Code |
| — Flood control / drainage | 40 | 0.027 / 0.117 / 0.254 | | |

- **Sources:** https://comptroller.texas.gov/taxes/property-tax/rates/index.php (2025 XLSX files:
  school-district, city, county, special-district) and the Comptroller's levy series via Texas
  Policy Research, https://www.texaspolicyresearch.com/texas-property-tax-levies-1998-2025/ .
- **Confidence:** medium. The files have one row per unit per appraisal district (split units).
  ISD rows (1,549) outnumber districts (about 1,020), so these percentiles are rough. Name matching
  for special district types is approximate. The 2025 levy totals are the Comptroller's.
- A typical urban homeowner pays ISD + county + city + junior college + hospital district (e.g.
  Harris, Dallas, Bexar, Tarrant), and often a MUD or ESD outside city limits. Combined rates of
  1.8-2.6 per $100 are common. medium.

---

## 6. Appraisal and homestead eligibility

### 6.1 Market value, Jan 1 assessment date
- **Rule:** All taxable property is appraised at market value as of Jan 1. Mass appraisal must follow
  USPAP. Reappraisal happens at least every 2 years (s. 25.18; not checked today).
- **Citation:** Tax Code s. 23.01(a)-(b); s. 1.04(7) (market value definition).
- **Quote:** "all taxable property is appraised at its market value as of January 1." (s. 23.01(a)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.23.htm#23.01
- **Confidence:** high.
- **Terms:** *market value* → *appraised value* (after the 10% or 20% cap, or productivity value) →
  *taxable value* (after exemptions). Unlike Florida there is no separate "assessed value", except
  that s. 11.13(a) and s. 11.22 say "assessed value". Treat it as appraised value. medium.

### 6.2 Agricultural / open-space valuation (note only)
- 1-d-1 open-space (ag/timber) land is valued on productivity, not market (Tax Code ch. 23
  subch. D-E). The homestead cap (s. 23.23(d)) and the circuit breaker (s. 23.231(c)) don't apply to
  it. A home on ag land can be a homestead (up to 20 acres) while the rest is valued as ag. Rollback
  tax when use changes. Not modelled for owner-occupied homes beyond noting that some rural homestead
  land rows will show productivity value. Confidence high (existence).

### 6.3 Homestead definition and eligibility
- **Rule:** A structure (including a mobile home) or a separately secured unit, plus up to 20 acres
  owned with it, that the owner (or a qualifying trust's trustor/beneficiary, or a surviving spouse
  with a life estate) **occupies as the principal residence**. Co-op shares qualify (s. 11.13(o)).
  One homestead per person per year (s. 11.13(h)). The applicant must state they claim no other
  homestead in Texas or elsewhere (s. 11.43(j)(2)).
- **Qualification date:** eligibility and amount are set by status on **Jan 1** (s. 11.42(a)).
  Exceptions:
  - over-65/disabled (s. 11.13(c)-(d)) and ss. 11.132-11.134, 11.136 apply for the full year in
    which the person qualifies (s. 11.42(c))
  - since 2022 (SB 8, 87th 2nd C.S.), a buyer may claim the general homestead exemption for the rest
    of the purchase year, if the seller didn't get it (s. 11.42(f))
  - 100% disabled veteran: prorated from qualification (s. 11.42(e))
- **Temporary absence:** a home keeps its homestead status during an absence of under 2 years with
  intent to return, or during military service or a stay in a care facility (s. 11.13(l)).
- **Application:** once granted, it carries forward until ownership or eligibility changes
  (s. 11.43(c)). It requires a Texas driver's license or ID, with exceptions (s. 11.43(j)(4)). The
  deadline is before May 1 (s. 11.43(d)), and late applications are allowed up to 2 years after the
  delinquency date (s. 11.431(a)). Appraisal districts may re-require an application only with a
  stated reason (s. 11.43(c-1)).
- **Quote:** "is occupied as the individual's principal residence by an owner" (s. 11.13(j)(1)(D)).
- **Quote:** "A person may not receive an exemption under this section for more than one residence
  homestead in the same year." (s. 11.13(h)).
- **URL:** https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.13 ;
  https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.42 ;
  https://statutes.capitol.texas.gov/Docs/TX/htm/TX.11.htm#11.43
- **Confidence:** high.
- **2025 changes to eligibility:** none to the s. 11.13(j) definition or the one-homestead rule.
  2025 changes were procedural: HB 2508 added s. 11.136 to s. 11.42(c) and s. 11.43(c); SB 850
  changed late applications and refunds; HB 2723 and HB 2730 changed application details (not
  read). Take-up counts by year are in `docs/research/texas_homestead_takeup.md`. medium on "no
  substantive change". HB 2723 and HB 2730 should be read.

---

## 7. Proposals and bills that are NOT law for 2026

| Proposal | Status | Source |
|---|---|---|
| SB 10 (89th 2nd C.S.): VAR 3.5% → 2.5% for cities/counties of 75,000+ (Senate); House version 1% for all with a public-safety carve-out | Passed each chamber in different forms; died in conference when the session ended (Aug 2025). s. 26.04(c) unchanged | https://capitol.texas.gov/tlodocs/892/analysis/html/SB00010I.htm ; https://www.bondbuyer.com/news/texas-bill-to-curb-property-tax-revenue-increases-fails-to-pass |
| HB 9 engrossed version: $250,000 BPP exemption from 2025 | Superseded; enrolled law is $125,000 from 2026 (s. 11.145) | https://capitol.texas.gov/tlodocs/89R/analysis/html/HB00009E.htm |
| SB 322 (89R): extend circuit breaker to 2031 and cut it to 10% | Not enacted; s. 23.231(k) still expires Dec 31, 2026 | https://capitol.texas.gov/tlodocs/89R/billtext/html/SB00322I.htm |
| HB 4407 and similar: deeper school compression (e.g. 15¢) | Not enacted; compression came through the GAA (about 6.8¢) | search results only |
| Bills to eliminate school M&O taxes / raise the sales tax | Not enacted (interim studies) | — |
| Interim 2026 proposals for the 90th Legislature (Jan 2027) | Not law; watch for policy comparisons | — |

---

## 8. Open questions

1. **County and city percentage exemptions and over-65 amounts:** these need a unit-by-unit table for
   2026 (appraisal district exemption tables or roll exemption codes). The Comptroller doesn't publish
   one statewide list. Which source covers the ~240 appraisal districts we won't have rolls for?
2. **Ceiling history:** s. 11.26(a-10) runs from each frozen homestead's prior-year tax and taxable
   value. Do the bulk rolls carry the ceiling amount (most do, as a "freeze" or ceiling field)? If not,
   we need a way to estimate it (e.g. qualify year × compression history since 2019).
3. **Which county/city/junior college units adopted a s. 11.261 freeze, and in which year?** The
   freeze base year can't predate adoption.
4. **Ordering of the (n) percentage vs dollar exemptions:** confirm on the rolls that the percentage
   is applied to appraised value (not net of $140k etc.) and how the $5,000 minimum interacts.
5. **"Assessed" vs "appraised" value** for s. 11.13(a) (FMFC $3,000) and s. 11.22: confirm on the
   rolls that they are taken from capped appraised value.
6. **TY2025 compression size:** the TY2024 MCR ($0.6669) and the GAA's exact state compression
   percentage for 2025-26 weren't checked against a primary TEA/GAA source. The "6.8 pennies" figure is
   the Senate Research Center's.
7. **TY2027+ MCR path:** the state compression percentage for 2027-28 depends on the 2027 GAA
   (90th Legislature). Baseline assumption: current-law formula with GAA value growth, no new
   compression. Daniel to confirm.
8. **Circuit breaker after 2026:** current law ends it. The baseline should let it lapse in 2027.
   Should a scenario keep it?
9. **Unused increment rate** (s. 26.013) and **HB 30 disaster rate** changes: read the full current
   text before coding the rate-setting module, if the model simulates rates rather than taking adopted
   rates as given.
10. **ESD 10¢ cap and hospital district caps** (Health & Safety Code): not verified today.
11. **SB 1453 debt-rate rule:** check its effect on 2026 I&S rates (probably small).
12. **Proposition numbers:** Wikipedia's table maps Prop 11 to SJR 85 (over-65 $60k) and Prop 10 to
    SJR 84 (fire). One secondary source disagreed. Check the Secretary of State's canvass if numbers
    are cited on the page.
13. **Over-65 take-up timing:** the full-year rule in s. 11.42(c) means age 65 at any point in the
    year qualifies. The model should use age ≥ 65 by Dec 31 (ACS age at interview, adjusted).
14. **Disabled definition:** s. 11.13(m) ties "disabled" to Social Security disability eligibility.
    Proxy from ACS disability + SSDI/SSI receipt? Needs a decision.
