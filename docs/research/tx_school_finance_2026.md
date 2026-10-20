# Texas school finance for 2026-27 (tax year 2026): formulas, parameters, data

Research notes for the district-by-district Texas model. Compiled 2026-10-20.

How this was checked: statute text was pulled from the Texas Legislature's statute files (current text, including the 89th Legislature's 2025 amendments). TEA letters and files were downloaded. The formulas were then checked against TEA's own Summary of Finances (SOF) data. "Verified in SOF" means the formula reproduces TEA's district numbers to the dollar for the districts tested.

Confidence key: **High** = statute text plus TEA data agree. **Medium** = statute or TEA, but not both, or the reading involves some interpretation. **Low** = inferred.

Statute links. The public site (statutes.capitol.texas.gov) is now a JavaScript app: deep links such as `https://statutes.capitol.texas.gov/Docs/ED/htm/ED.48.htm#48.2551` work in a browser but return an empty shell to scripts. Scripts can read the raw chapter files at `https://tcss.legis.texas.gov/resources/ED/htm/ED.48.htm` (likewise `ED.45`, `ED.46`, `ED.49`, `TX/htm/TX.11`, `TX/htm/TX.26`, `GV/htm/GV.403`).

---

## 0. The 2025 law changes in one place

| Change | Bill | Effect on the formula | Confidence |
|---|---|---|---|
| Homestead exemption $100,000 -> **$140,000** (Tax Code 11.13(b)) | SB 4 + SJR 2 (approved Nov 4, 2025) | Lowers taxable value (T2) from TY 2025. Hold-harmless aid under 48.2543(a-2), and I&S aid under 46.071(a-3) | High |
| Over-65/disabled extra exemption $10,000 -> **$60,000** (11.13(c)) | SB 23 + SJR 85 (approved Nov 2025) | Same mechanism. Hold-harmless under 48.2543(a-3) | High |
| MCRs for 2025-26 computed "as if" the exemption had taken effect | SB 4 s. 2.02, SB 23 s. 2.01 (48.2551(d-3), (d-5)) | Value growth for the 2.5% rule is measured on post-exemption values, so most districts got no local compression in TY 2025 | High |
| Basic allotment = **$6,160 + GYIA** (guaranteed yield increment adjustment), with GYIA set at **$55** for FY 2026-27, so BA = **$6,215** | HB 2 s. 1.10, 7.18 (48.051, 48.2561) | Raises Tier One entitlement. Golden-penny growth now flows to the BA instead | High (verified in SOF) |
| Golden-penny yield fixed at **BA x 0.02084** = $129.52; copper = BA x 0.008 = $49.72 | HB 2 s. 7.17 (48.202(a-1)) | Golden yield no longer floats with the 96th-percentile wealth level. Repeal of 48.202(f) ends copper-penny compression when the BA rises | High (verified in SOF) |
| Teacher Retention Allotment ($2,500/$5,000 for large districts, $4,000/$8,000 for small districts, by experience) | HB 2 s. 7.16 (48.158) | Subchapter D, so it enters the Tier One entitlement that sets the recapture threshold. It is not in WADA | High |
| Allotment for Basic Costs, $106 per enrolled student | HB 2 (48.161) | Subchapter D, same as above | High (statute). The FY 2026 vs 2027 phase-in was not checked |
| Additional state compression of **3.31 points** in FY 2026 | GAA (SB 1) TEA riders, under 48.2552(c) | State MCR TY 2025 = $0.6322 | High |
| Business personal property exemption, first $125,000 | HB 9 + HJR 1 | Lowers T2 ("PERSONAL PROP FIRST 125K" column in the PVS). No Ch. 48 hold-harmless. The normal formula absorbs it | Medium |
| No new compression for TY 2026 beyond the formula | GAA rider: TY 2026 growth 3.60%. TEA: "- 0.0000" | State MCR TY 2026 = $0.6254 | High |

Note on the GAA figures. The enrolled GAA (SB 1) still prints pre-HB 2 values: BA $6,160; golden yield $132.40 (FY 2026) and $140.02 (FY 2027); copper $49.28. TEA does not use them. The SOF and TEA's July 15, 2026 recapture letter use $6,215, $129.52 and $49.72, which matches HB 2's statute and the GAA's HB 2 contingency appropriation (Art. IX, about $8.11 billion). **Use the statute values.**

---

## 1. Maximum compressed rate (MCR)

### Formula (Education Code 48.255, 48.2551, 48.2552)

Each district's MCR is the lower of a **local** and a **state** value. It is then raised, where needed, to a **floor** of 90% of the highest MCR, which in practice is the state MCR.

**State compression percentage (48.255(b)).** The lowest of:
1. 93%, or a lower percentage set by appropriation;
2. `SCP = PYCP x 1.025 / (1 + ECPV)`, where ECPV is the estimated statewide value growth (the Comptroller's estimate in the GAA);
3. the prior year's SCP.

Any 48.2552(c) amount is then subtracted. That amount is the state savings from the floor, which the legislature chooses how to use.

```
State MCR_t = trunc4( State MCR_{t-1} x 1.025 / (1 + ECPV_t) ) - additional compression_t
```

TEA truncates to four decimals rather than rounding: 0.6322 x 1.025/1.036 = 0.62549, which TEA reports as 0.6254.

**Local MCR (48.2551(b)):**

```
if DPV_t >= 1.025 x PYDPV:   MCR_local = 1.025 x (PYDPV + E) x PYMCR / DPV_t
else:                        MCR_local = PYMCR
MCR = min(MCR_local, State MCR)
MCR = max(MCR, 0.90 x State MCR)          # 48.2552(b) floor
```

- DPV is the TEA estimate of current-year state taxable value (a "T2"-type value). It is built from locally certified July 25 values and adjusted under Gov't Code 403.302(d). TEA's template computes `est. TY2026 T2 = TY2025 Comptroller T2 x (TY2026 July-25 local value / TY2025 July-25 local value)`, with adjustments for local optional homestead exemption changes.
- PYDPV is last year's Comptroller-certified value. E is value released this year from expiring Ch. 313 limitations or TIF exclusions.
- Short quote, 48.2551(a)(3): the MCR is the rate at which a district "must levy a maintenance and operations tax to receive the full amount of the tier one allotment".
- Short quote, 48.2552(b): if a district's MCR "would be less than 90 percent of another school district's maximum compressed rate", it is raised to that 90% level.
- Districts that skip the Local Property Value Survey (LPVS) get "the lesser of the state maximum compression rate of $0.6254 or their prior-year MCR" (TEA, Aug 27, 2026).

### Parameters

| | TY 2024 (SY 2024-25) | TY 2025 (SY 2025-26) | TY 2026 (SY 2026-27) |
|---|---|---|---|
| ECPV (GAA) | n/a | 5.60% | 3.60% |
| Additional compression | n/a | 0.0331 (GAA rider, 48.2552(c)) | 0.0000 |
| State MCR | $0.6855 | 0.6855 x 1.025/1.056 - 0.0331 = **$0.6322** | 0.6322 x 1.025/1.036 = **$0.6254** |
| Floor (90%) | $0.6169 | $0.5689 | $0.5628 |
| Max M&O rate (MCR + $0.17, 45.003(d)) | $0.8555 | $0.8022 | $0.7954 |
| Districts at state MCR / at floor (of 1,013 ISDs) | n/a | 199 / 70 | 162 / 118 |

In the final lists, 0.6169 is the most common MCR in both years (403 districts in 2025, 207 in 2026). These are districts that sat at the old TY 2024 floor and had less than 2.5% growth on post-exemption values, so they kept their prior MCR.

**Effect of an exemption on compression.** An exemption increase cuts measured DPV growth. That switches districts from local compression to "MCR = PYMCR". It also lowers future local compression, because PYDPV is lower, though growth is measured from the lower base. A model must carry DPV and MCR forward year by year.

**Sources and confidence**
- Statute: ED 48.255, 48.2551, 48.2552 (High).
- TEA TAA letter, June 18, 2026: https://tea.texas.gov/taa-letters/tax-year-2026-maximum-compressed-tax-rates (PDF: https://tea.texas.gov/sites/default/files/taa-letters/taa-2026-06-18-tax-year-2026-maximum-compressed-tax-rates.pdf, verified). Quote: "TY 2026 State Compression Rate: 0.6322 x (1.025 / 1.036) - 0.0000 = $0.6254".
- TEA TY 2025 letter: https://tea.texas.gov/about-tea/news-and-multimedia/correspondence/taa-letters/tax-year-2025-maximum-compressed-tax-rates. Quote: "0.6855 x (1.025 / 1.056) - 0.0331 = $0.6322".
- GAA SB 1 (89R), TEA rider: "the state compression percentage ... shall be reduced by 3.31 percentage points". Property Tax Relief rider 76(d) gives $767.1 million for the biennium. https://capitol.texas.gov/tlodocs/89R/billtext/pdf/SB00001F.pdf (verified, 10 MB).
- Final MCR letter, Aug 27, 2026: https://tea.texas.gov/taa-letters/final-maximum-compressed-tax-rates-mcr-and-adoption-tax-rate-tax-year-2026 (High).

---

## 2. Tier One: entitlement, local share, state aid

### Formula

**Basic allotment (48.051(a)).** Per student in ADA (average daily attendance, excluding special-education and career-tech time):

```
A = min( BA ,  BA x TR / MCR )         BA = $6,160 + GYIA = $6,215
```

A district that levies below its MCR (TR < MCR) gets a proportionally lower BA. The SOF's `DISTRICT_BA` ranges from $5,345 to $6,215.

**Tier One entitlement.** This is the sum of the allotments under Subchapters B (basic), C (student-based: special ed, comp ed, bilingual, CTE, small/mid-size, early ed, G/T, CCMR, fast growth, TIA ...) and D (transportation, NIFA, TRA, support staff retention, safety, basic costs ...). These are the 48.266(a)(1) entitlement. The SOF field is `TIER_I_TOT_COST_P2`.

**WADA (weighted ADA, 48.202(a)):** "(sum of Subchapter B and C allotments) / basic allotment". Subchapter D allotments are excluded. SOF field: `TIER_II_WADA`.

**Local share (local fund assignment, LFA; 48.256):**

```
LFA = TR x DPV / 100       TR = Tier One M&O rate = min(adopted M&O rate, MCR) (45.0032(a))
                            DPV = Comptroller-certified current-year taxable value, i.e. T2
```

LFA is computed at 100% collection on the state value, not on actual collections. Austin: 0.6254 x 172,746,537,602/100 = $1,080,356,846 = SOF `TIER_I_LOCAL_SHARE`. Verified.

**Tier One state aid (48.266(c)):**

```
S1 = max(0, Entitlement - ASF - LFA)
```

ASF is the Available School Fund per-capita distribution, $470.81 per ASF ADA in 2025-26 and $683.87 in 2026-27 (`ASF_RATE`). Fort Worth 2026-27: 633,225,300 - 40,917,761 - 329,421,553 = 262,885,986 = SOF `TIER_I_STATE_SHARE`. Verified.

Quote, 48.256(a): "LFA = TR X DPV" where DPV is "the taxable value of property in the school district for the current tax year".

### Parameters (ISDs only, 1,013 districts, SOF LPE runs)

| | 2025-26 near-final (run 47224) | 2026-27 preliminary (run 47363) |
|---|---|---|
| BA | $6,215 | $6,215 |
| Tier One entitlement | $45.83 bn | $47.25 bn |
| LFA | $25.49 bn | $25.51 bn |
| Tier One state share | $20.67 bn | $20.89 bn |
| ASF | $2.18 bn | $3.12 bn |
| T2 value (CPTD) | $4,135 bn | $4,202 bn |
| WADA (Tier Two) | 6.85 m | 7.05 m |

Sources: ED 48.051, 48.256, 48.266; TEA SOF data (Section 7). Confidence: High.

---

## 3. Tier Two: golden and copper pennies

### Formula (48.202, 48.203, 45.0032(b), 45.003(d))

Enrichment rate DTR is the M&O rate above the MCR, capped at $0.17 (45.003(d), 48.203).
- **Golden pennies** are the first 8 cents above the MCR (45.0032(b)(1)). Their guaranteed level is GL1 = BA x 0.02084 = **$129.52** per WADA per cent. No voter approval is needed for the first 5 (Tax Code 26.08(n)). Golden pennies are **never recaptured** (48.257(d)), and the DTR cap does not apply to them (48.202(a-2)).
- **Copper pennies** are the next 9 cents (up to 17 cents in total). Guaranteed level GL2 = BA x 0.008 = **$49.72**. Local revenue above $49.72 per WADA per cent is **recaptured** (48.257(f)).

```
GYA = GL x WADA x DTR x 100 - LR,    LR = DTR x DPV/100     (computed separately for each level, floored at 0)
```

Equivalent per cent of tax effort, with yield y = DPV / (10,000 x WADA):

```
golden aid per cent  = WADA x max(0, 129.52 - y)       local kept in full
copper aid per cent  = WADA x max(0, 49.72  - y)
copper recapture/cent = WADA x max(0, y - 49.72)        (on collections)
```

The wealth thresholds follow: equalization stops at DPV/WADA = $1,295,200 (golden) and $497,200 (copper).

DTR in the SOF is computed from collections: `(M&O collections - LFA)/(DPV/100)`, split by level as `TIER_II_DTR_LV2` (golden) and `TIER_II_DTR_LV3` (copper). The level-1 fields are unused and always zero.

**Verified in SOF.** Fort Worth 2026-27: (51,672,789 + 39,782,632)/(94,779.922 x 7.45) = $129.52. Austin 2025-26 copper: (156,996,733 - 118,423,390)/(87,860.861 x 8.83) = $49.72.

**Voter-approval rate (Tax Code 26.08(n)):** MCR + greater of (last year's enrichment rate, $0.05) + debt rate.

| | 2025-26 | 2026-27 |
|---|---|---|
| Golden yield | $129.52 | $129.52 |
| Copper yield | $49.72 | $49.72 |
| Golden state aid (ISDs) | $3.52 bn | $3.49 bn |
| Copper state aid (ISDs) | $0.25 bn | $0.26 bn |

Quote, 48.202(a-1)(1): golden is "the maximum amount of the basic allotment ... by 0.02084, for the first eight cents".

Sources: ED 48.202, 48.257(d)-(f); TEA ELR letter, July 15, 2026: "exceeds the Tier Two (level two) guaranteed yield of $49.72" (https://tea.texas.gov/about-tea/state-funding/excess-local-revenue/annual-review-of-local-revenue-2026-2027.pdf, verified). Confidence: High.

**GYIA for 2027-28 onward.** 48.2561(a) sets GYIA each biennium: the per-WADA cost of keeping the golden yield at the 96th percentile of wealth, minus the cost at BA x 0.02084. TEA had to fix it by Oct 1, 2026, but I could not find a published figure (open question).

---

## 4. Recapture (excess local revenue, Ch. 49)

### Formula (48.257, 49.153)

**Tier One.** A district is subject to recapture if LFA > Entitlement - ASF. The amount owed is computed on **actual M&O collections** at the Tier One rate:

```
R1 = max(0, C1 - (Entitlement - ASF))           C1 = Tier One M&O collections (SOF MO_COLL_LV1)
```

Verified: Austin 2026-27, 1,014,485,688 - (629,257,581 - 41,975,662) = 427,203,769 = `OP3_RECAP_AMT_LV1`.

**Copper.** `R3 = max(0, copper local revenue - 49.72 x WADA x DTR3 x 100)`. Austin 2026-27: 145,970,824 - 49.72 x 93,877.158 x 8.45 = 106,529,838 = `OP3_RECAP_AMT_LV3`. Verified.

**Golden:** none.

**Adjustments:**
- 48.257(b): if collections after recapture fall short of the entitlement, recapture is reduced. 48.257(b-1) then gives aid of up to the TRA amount (`ASA_RECAPHH_AMT`, $74 million statewide in 2026-27).
- 48.257(c): other Ch. 48 state aid can be "netted" against recapture.
- 48.283: aid for districts hurt by the SB 2 (2023) compression ($74 million).

The rough Tier One wealth threshold is (Entitlement - ASF)/WADA / (MCR/100), about $6,256/0.006254 = **about $1.0 million T2 value per WADA** (Austin). Districts above about $497,200 per WADA with copper pennies pay copper recapture.

| | 2025-26 | 2026-27 prelim |
|---|---|---|
| Districts paying recapture | 202 (94 Tier One) | 203 (90 Tier One) |
| Total recapture | $2.59 bn (T1 $2.17 bn + copper $0.42 bn) | $2.18 bn (T1 $1.77 bn + copper $0.41 bn) |

Quote, 49.153(a): "The total cost of credit is the amount of the district's maintenance and operations tax revenue that exceeds the level established under Section 48.257."

Sources: ED 48.257, Ch. 49; TEA Excess Local Revenue page https://tea.texas.gov/about-tea/state-funding/excess-local-revenue (verified). Confidence: High.

---

## 5. Hold-harmless and other state aid tied to exemptions and compression

### 5a. 48.2543: additional state aid for the homestead exemption (ASAHE)

- (a-2): from 2025-26, $140,000 exemption (SB 4). (a-3): from 2025-26, $60,000 over-65/disabled exemption (SB 23). Earlier layers: (a) 2021 $25k->$40k and (a-1) 2023 $40k->$100k; under the text these ran only through 2024-25 (see open question 2).
- The test compares current-law state and local revenue under Ch. 48 and 49 with what the district would have had "under this chapter and Chapter 49 as those chapters existed on September 1, 2024", without the 2025 exemption increase.
- The counterfactual M&O rate is the lesser of the current rate and the 2024 adopted rate (48.2543(b)(3)).

```
ASAHE = max(0, Rev_prior-law,no-increase - Rev_current-law)
Rev = M&O collections + Tier One state aid + Tier Two aid + other programs - recapture
```

The SOF fields are `mo_asahe_*` sheets: `PL_ASAHE`, `CL_ASAHE`, `ASAHE`, `SAG` (state aid gain), `MOLE`, `RECAP_DIFF`, `TIER_I_ALLOT_DIFF`, plus scenario columns `_100K_`, `_L60K_`, `_40K`.

**Finding: the 2025 hold-harmless pays almost nothing.**
- SOF 2025-26 near-final: **$1.17 million in total**, one district (Deer Park ISD).
- SOF 2026-27 preliminary: **$0**.

The reason is that the counterfactual is the **Sept 1, 2024 law**, so it lacks the HB 2 increases (BA +$55, TRA, basic costs, and others). In the SOF, `TIER_I_ALLOT_DIFF` is about $3.27 billion statewide in 2026-27. That gain more than offsets the exemption losses, which fall mainly on golden pennies in districts above $1.295 million per WADA.

Quote, LBB fiscal note: "Districts that experienced a revenue decrease would receive additional state aid through the FSP to largely offset revenue losses."

LBB cost estimates (largely the normal formula, not the hold-harmless):
- SB 4: $1.32 billion in FY 2026 and $1.42 billion in FY 2027, including recapture losses of $337 million and $410 million.
- SB 23: $577 million and $630 million.

Confidence: statute High. "Near zero because of the HB 2 offset" is Medium-High: the SOF numbers are certain, the mechanism is inferred from the SOF fields.

### 5b. 48.2542: aid for the tax-ceiling reduction (over-65/disabled frozen levies)

When compression lowers the MCR, Tax Code 11.26(a-10) lowers each frozen homestead's ceiling by `prior taxable value x (PYMCR - MCR)`. It also lowers the ceiling by the increase in the 11.13(b)/(c) exemptions times the current rate. 48.2542 fully compensates the district for the lost revenue if the formula does not. Comptroller T-values separate out ceiling-adjusted values (403.302(j-1)).

SOF field: `ASAHE_065`, $448 million in 2025-26 and **$549 million in 2026-27** (868 districts).

Quote, 48.2542: "additional state aid in the amount necessary to fully compensate the district". Confidence: High.

### 5c. Other

- **46.071 (a-3)/(b-3):** I&S (debt) hold-harmless for the $140k and $60k exemptions, limited to debt eligible as of Sept 1, 2025. SOF sheet `is_asahe_*`. This only matters if the model covers I&S.
- **48.283:** SB 2 (2023) compression aid ($74 million, 29 districts, 2026-27).
- **48.259:** local optional homestead exemption: funding values deduct only half its loss (403.302(d)(2)). That is the T2 vs T4 distinction.

**There is no "48.2544" in current law.** The 2019-23 compression hold-harmless items (48.2555 etc.) have expired or been repealed. A future exemption increase would need its own new subsection.

Sources: ED 48.2542, 48.2543, 48.283, 46.071. SB 4 enrolled text https://capitol.texas.gov/tlodocs/89R/billtext/html/SB00004F.htm and fiscal note https://capitol.texas.gov/tlodocs/89R/fiscalnotes/html/SB00004F.htm (both verified). SB 23 fiscal note https://capitol.texas.gov/tlodocs/89R/fiscalnotes/html/SB00023F.htm (verified).

---

## 6. How value, exemption and compression changes flow through

Notation: V = T2 value; M = MCR; g = golden cents; c = copper cents; W = WADA; y = V/(10,000 W).

| Change | Taxpayers (district M&O levy) | District revenue | State |
|---|---|---|---|
| dV < 0, district below every threshold (y < 49.72, V/W < about $1.0m) | -(M + g + c) x dV/100 | **0**: LFA and enrichment local losses are replaced by aid | Pays (M + g + c) x dV/100 |
| 49.72 < y < 129.52 with copper pennies | same | 0: copper loss offset by lower copper recapture | Loses copper recapture plus Tier One and golden aid |
| Tier One recapture district (y > 129.52) | same | **-g x dV/100** (golden is not equalized). Tier One and copper are offset by lower recapture | Loses recapture of (M + c) x dV/100 |
| Homestead exemption increase | Same as dV but concentrated on homesteads. Frozen (65+) homesteads only gain via 11.26(a-10) | Same as dV, then 48.2543 tops up if below the counterfactual. Currently about $0 because of the 2024-law baseline | Same plus any ASAHE and 48.2542 |
| Exemption effect on next year's MCR | Lower measured DPV growth -> less local compression in t+1 (MCR = PYMCR more often) -> a higher future MCR than otherwise | Neutral for Tier One revenue | The state saves compression cost later |
| State compression (State MCR down dm) | -dm x V/100 for districts at state MCR. The cap on the M&O rate falls by dm | 0 for Tier One (entitlement fixed). 48.2542 compensates ceilings | Pays dm x V/100 (non-recapture) or loses recapture |
| Rate below MCR | Lower | BA cut in proportion to TR/MCR | |

**Timing.** Funding for school year t uses **tax year t values**: since HB 3 (2019), DPV is the current-year Comptroller value. Payments start on GAA estimates (TY t-1 x 1.036 for 2026-27). They are updated with the preliminary PVS around February of t+1, and settled up with the final PVS around August of t+1 (TY 2025 final certified Aug 27, 2026). Under 403.302(c), the Comptroller's value is presumed to be the local value if the local value is within 5% (the margin of error). Otherwise the state value is used, unless the local value is higher.

---

## 7. Data needed and where to get it (all URLs checked 2026-10-20)

| Need | Source | URL | Format | Status |
|---|---|---|---|---|
| District SOF, 2026-27 | TEA SOF data download, Run ID 47363 ("Preliminary") | https://tea.texas.gov/about-tea/state-funding/fy2026-2027-sof-data.xlsx | XLSX, 7.1 MB. Sheets `inputs_lpe/dpe` (254 cols), `outputs_lpe/dpe` (241 cols), `mo_asahe_lpe/dpe` (77), `is_asahe_lpe/dpe` (39). 1,231 rows (1,013 ISDs = `DISTRICT_TYPE_CD`=1, plus charters) | **No near-final exists yet for 2026-27.** Near-final comes about fall 2027 |
| District SOF, 2025-26 | TEA, Run ID 47224 "Near Final" | https://tea.texas.gov/about-tea/state-funding/fy2025-2026-sof-data.xlsx | XLSX, 7.3 MB, same layout | Verified |
| Earlier SOF | 2024-25 final (46820), 2023-24 final (45525) | https://tea.texas.gov/about-tea/state-funding/fy-2024-2025-sof-run-id-46820-final-data_0.xlsx ; https://tea.texas.gov/data-reports/financial-reports/school-finance-reports-and-data/2023-2024-sof-run-id-45525.xlsx | XLSX | Listed on the State Funding page |
| SOF field definitions | TEA SOF data dictionary (2024-25 runs) | https://tea.texas.gov/about-tea/state-funding/fy-2025-summary-of-finance-data-dictionary-state-funding-and-ffa-split2.pdf | PDF | Verified. Layout text is jumbled, so read it visually |
| SOF data timing | "Data Elements, Sources, and Timelines" (Feb 2026) | https://tea.texas.gov/about-tea/state-funding/foundation-school-program/fsp-hot-topics/state-funding-data-elements-sources-and-timelines-feb2026.pdf | PDF | Verified |
| Individual SOF reports | TEA FSP reports app | https://tealprod.tea.state.tx.us/Tea.FspReports.Web/ | Web | Listed |
| MCR by district TY 2026 (final) | TEA | https://tea.texas.gov/about-tea/state-funding/ty2026-final-mcrs.pdf | PDF, 1,013 rows. **Use `pdftotext -raw`**: `-layout` misaligns names and IDs. Values equal SOF `inputs_lpe.MAX_COMPR_RATE` (0 differences) | Verified |
| MCR TY 2025 (final) | TEA | https://tea.texas.gov/about-tea/state-funding/ty2025-final-mcrs-2.pdf | PDF | Verified |
| MCR history TY 2018-2024 | TEA | https://tea.texas.gov/about-tea/state-funding/mcr-for-tax-years-2018-2024-2.xlsx | XLSX | Verified |
| MCR calculator plus district inputs | TEA "2026-27 Tax Rate and MCR Template v2" | https://tea.texas.gov/about-tea/state-funding/2026-27-tax-rate-and-mcr-template-finalv2.xlsx | XLSX. `Tax Data` sheet has, per district: TY 2025 T2 and T4, local optional homestead loss, 313/TIF expirations, 2025 adopted M&O rate, MCR, golden and copper pennies | Verified |
| PVS by district, TY 2025 final (T1-T22, local vs Comptroller vs assigned, by category, exemption losses incl. "LOSS INCR HMSTD", BPP $125k, freeze) | Comptroller SDPVS 2025 Final (certified Aug 27, 2026) | https://comptroller.texas.gov/taxes/property-tax/docs/2025-final-isd-worksheet-export-summary.xlsx (1.2 MB) ; detail: `.../2025-final-isd-worksheet-export-detail.xlsx` ; self-report: `.../2025-final-isd-self-report-export-summary.xlsx` (2.0 MB) ; index: https://comptroller.texas.gov/taxes/property-tax/pvs/2025f/index.php | XLSX. Key `TU ID` = "001-902-02" (county-district-02); `ASGN T2` = funding value | Verified (Cayuga ASGN T2 = TEA template T2) |
| PVS TY 2026 | Comptroller preliminary (expected around Jan-Feb 2027), final (around Aug 2027) | https://comptroller.texas.gov/taxes/property-tax/pvs/ | XLSX | Not yet published |
| Short T-value table | TEA "CPTD 2025 final" | https://tea.texas.gov/about-tea/state-funding/additional-finance-resources/cptd-2025-final-data.xlsx | XLSX: T1, T2, T3, T4, T8, local roll, assigned value. Column labels still say "$100,000" | Verified |
| Adopted M&O/I&S rates | TEA history 2005-06 to 2024-25 | https://tea.texas.gov/about-tea/state-funding/additional-finance-resources/school-district-adopted-tax-rates-1.xlsx | XLSX (no 2025-26 column yet) | Verified |
| Adopted rates TY 2025 | Comptroller ISD rates and levies (with NNR/VATR) | https://comptroller.texas.gov/taxes/property-tax/docs/2025-school-district-rates-levies.xlsx | XLSX, Detail plus Summary. 2026 file returns **404 (not yet out)** | Verified |
| Adopted rates TY 2026 | Not yet consolidated. The SOF 2026-27 `PY1_MO_RATE_ADOPT` / `I_S_RATE` is a TEA estimate (prior rate adjusted for MCR change). TEA says total M&O rates will be updated by Feb 2027; the Comptroller 2026 rates file is expected around Jan-Feb 2027 | n/a | n/a | Gap: use 2025 rates minus MCR change, flagged |
| ADA, WADA, enrollment | SOF fields `ADA_TOT_REFINED`, `TIER_II_WADA`, `TOT_ENROLL` | (SOF above) | | Verified |
| | TEA ADA and wealth per ADA history 2005-2025 | https://tea.texas.gov/about-tea/state-funding/state-funding-reports-and-data/wealth-per-ada-2005-2025.xlsx | XLSX | Verified |
| Recapture letters | TEA ELR page (2026-27 notification, 2025-26 near-final ELR letter) | https://tea.texas.gov/about-tea/state-funding/state-funding-reports-and-data/2025-2026-near-final-elr-letter.pdf | PDF | Verified |
| Statute (raw files) | Texas Legislature | https://tcss.legis.texas.gov/resources/ED/htm/ED.48.htm (also ED.45, ED.46, ED.49, TX/htm/TX.11, TX/htm/TX.26, GV/htm/GV.403) | HTML | Verified |
| HB 2 enrolled and fiscal note | Capitol | https://capitol.texas.gov/tlodocs/89R/billtext/html/HB00002F.htm ; https://capitol.texas.gov/tlodocs/89R/fiscalnotes/html/HB00002F.htm | HTML | Verified (no enrolled bill analysis: 404) |
| GAA 2026-27 | Capitol | https://capitol.texas.gov/tlodocs/89R/billtext/pdf/SB00001F.pdf | PDF. TEA riders around Art. III pp. 6 and 31 | Verified |

Notes on SOF fields most useful for the model (all on `outputs_lpe` unless noted):
- Tier One: `TIER_I_TOT_COST_P2` (entitlement), `TIER_I_LOCAL_SHARE` (LFA), `TIER_I_STATE_SHARE`, `ASF_ALLOT`, `TIER_I_MO_TAX_RATE`, `DISTRICT_BA`, `CPTD_PROPERTY_VALUE` (T2 used).
- Tier Two: `TIER_II_WADA`, `TIER_II_DTR_LV2/LV3`, `TIER_II_LOCAL_REV_LV2/LV3`, `TIER_II_AID_LV2/LV3`.
- Collections and recapture: `MO_COLL_LV1/2/3`, `RECAPTURE`, `OP3_RECAP_AMT_LV1/LV3`.
- Totals and other aid: `TOT_STATE_AID`, `ASA_RECAPHH_AMT`, `ASA_TC_48_283`, `TCHR_GT5_ALLOT`, `TCHR_3_LT5_ALLOT`, `ABC_ALLOT`.
- Inputs: `MAX_COMPR_RATE`, `PY1_DPV_T1..T22`, `PY1_DPV_LOCAL`, `PY1_MO_RATE_ADOPT`, `I_S_RATE`, `PY1_MO_COLL_LOCAL`, `ACTUAL_FROZEN_LEVY`.
- Hold-harmless: `mo_asahe_lpe` has `ASAHE`, `ASAHE_065`, `SAG`, `MOLE` and the DPV/LFA/recapture differences by exemption scenario.
- In 2026-27 files "PY1" means the funding tax year (TY 2026).
- LPE = Legislative Payment Estimate (GAA assumptions, the basis for payments). DPE = District Planning Estimate (district-submitted values). Use LPE to match LBB and GAA totals.

---

## 8. Recommended simplifications

1. **Take entitlements from the SOF and hold them fixed across policy runs.** Tier One entitlement (`TIER_I_TOT_COST_P2`), WADA, ASF, BA and the Subchapter C/D allotments don't depend on property value, apart from the TR < MCR cut. Recompute only LFA, Tier One state aid, Tier One recapture, golden and copper aid, copper recapture, and the voter-approval rate (VATR).
2. **Use TEA's final TY 2026 MCRs for the base year.** Run the 48.2551/48.2552 formula only for 2027+ and for policy scenarios. Carry DPV, PYDPV and PYMCR by district. Truncate the state MCR to 4 decimals. Default future additional compression = 0. Future ECPV comes from the value forecast.
3. **Base-year values.** Use SOF 2026-27 `CPTD_PROPERTY_VALUE` (TEA's TY 2026 T2 estimate) and scale the model's roll-based T2 to it by district. Swap in the Comptroller's 2026 preliminary PVS when it appears. Use the PVS worksheet export's T-values to split homestead, over-65 and BPP exemption losses.
4. **Collections.** Use C = rate x local value x a district collection ratio, calibrated as `MO_COLL_LV1 / (TIER_I_MO_TAX_RATE x PY1_DPV_LOCAL/100)` from the SOF. Recapture uses collections, LFA uses T2 at 100%.
5. **Hold-harmless.**
   - Under current law, set the 48.2543 ASAHE to the SOF value (about $0).
   - For a policy that raises exemptions, the result depends on how the bill writes its hold-harmless. Offer two switches: (a) none, with the normal formula offset only; (b) 2025-style, which tops each district up to its pre-policy state plus local revenue, net of recapture, at the lesser of current or base-year M&O rate.
   - Take 48.2542 (`ASAHE_065`) from the SOF for the base year. Recompute as frozen-levy loss when MCR or exemptions change.
6. **Ignore second-order items, or take them from the SOF:** 48.257(b)/(b-1) adjustments, 48.283, fast-growth, TIA, CCMR, Ch. 313/TIF value details, and charter schools. Charters have no tax base, but changes in BA or the guaranteed yield (GY) affect their state cost; keep them only for statewide-cost totals.
7. **I&S.** Model the I&S levy as rate x T8/I&S taxable value. Treat EDA/IFA and 46.071 aid as fixed from the SOF `is_asahe` and EDA/IFA fields unless a policy targets debt.
8. **Pass-through framing for results.** For non-recapture districts, a value or exemption loss is a state cost, not a district revenue loss. For Tier One recapture districts, only golden-penny revenue is at risk. That makes the "who bears it" split quick to compute.

---

## 9. Open questions

1. **2026-27 near-final SOF doesn't exist yet.** The only 2026-27 file is preliminary run 47363, with TY 2026 values estimated as TY 2025 x 1.036 adjusted by the LPVS. Is that acceptable for the base year, or should we wait for the Feb-Mar 2027 update with preliminary PVS?
2. **Older 48.2543 layers.** As written, (a) is 2022-23 only and (a-1) is 2023-24 and 2024-25 only. The SOF still carries "prior law ASAHE" fields (`PL_ASAHE` = 0). I assumed those layers have ended. Confirm with TEA if it matters.
3. **ASAHE counterfactual MCR.** It is not clear whether TEA's "Sept 1, 2024 law" run keeps the actual TY 2025/26 MCR or recomputes it without the exemption. The SOF suggests the same MCR (MCRs were computed "as if" the exemption applied, 48.2551(d-3)), but TEA does not say so explicitly.
4. **GYIA for FY 2028-29** (48.2561(a), due Oct 1, 2026) was not found. It sets the 2027-28 BA and golden yield. The baseline needs a rule: hold $55, or estimate from the 96th-percentile formula.
5. **2027-28 state compression.** It depends on the 2027 GAA's ECPV and any 48.2552(c) amount (the 2025-26 one was 3.31 points, $767 million). Baseline: formula only, no extras (matches TX_DECISIONS.md).
6. **Basic costs allotment phase-in.** The statute says $106. I did not confirm whether FY 2026 was lower. It does not affect 2026-27.
7. **2026 adopted rates** are not yet compiled. Use 2025 rates adjusted for MCR changes, or the SOF estimate, and flag them.
8. **Circuit breaker expiry (Tax Code 23.231) after 2026** raises non-homestead T2 values in 2027+. That feeds the MCR formula and lowers future MCRs through local compression. It needs to be in the value projections.
9. **Charter schools and special districts** (`DISTRICT_TYPE_CD` not 1): exclude from district results, but keep them in state-cost totals when the BA changes.
