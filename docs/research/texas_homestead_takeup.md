# Texas homestead exemption claims around the 2022, 2023 and 2025 increases

Gathered 2026-10-16 to calibrate the Florida model's take-up response (projection setting
`takeup`), and kept for the Texas model. Counts are derived from the Comptroller's School District
Property Value Study (PVS) final findings; check before reuse.

## School homestead exemption history (Texas)
- $25,000 → $40,000: Prop 2, May 7, 2022 (tax year 2022). Worth about $175/yr per homestead
  (Sen. Bettencourt's projection, reported by Fox 7:
  https://www.fox7austin.com/election/texas-voters-approve-two-modest-property-tax-relief-measures).
- $40,000 → $100,000: SB 2 / Prop 4, approved Nov 7, 2023, retroactive to tax year 2023. $60k ×
  average school rate $1.136/$100 = **$681/yr** (Senate Research Center, SB 2, 88th 2nd called:
  https://capitol.texas.gov/tlodocs/882/analysis/html/SB00002I.htm).
- $100,000 → $140,000: SJR 2 / Prop 13, Nov 2025. $40k × $0.9086 = $363/yr
  (https://capitol.texas.gov/tlodocs/89R/analysis/html/SJ00002F.htm).
- Confound: SB 8 (87th, 2nd called; effective Jan 1, 2022) let buyers claim in the year of purchase
  (https://capitol.texas.gov/tlodocs/872/analysis/html/SB00008F.htm).

## Statewide homestead counts (derived)
Source pages: `https://comptroller.texas.gov/auto-data/PT2/PVS/{YEAR}F/ALL0000001Y.php`.
2018–2021 inferred as total state homestead exemption value ÷ $25k (slightly low: partial
exemptions); 2022–2024 = value lost to the $10k step ÷ $10k (effectively exact).

| Tax year | Homesteads | Change | ACS owner-occupied units (B25003) |
|---|---|---|---|
| 2018 | 5,198,000 | – | 6,034,082 |
| 2019 | 5,288,000 | +1.7% | 6,179,278 |
| 2020 | 5,367,000 | +1.5% | (no 1-yr ACS) |
| 2021 | 5,469,000 | +1.9% | 6,761,002 |
| 2022 | 5,756,000 | +5.3% | 6,926,616 (+2.4%) |
| 2023 | 5,947,000 | +3.3% | 7,048,369 (+1.8%) |
| 2024 | 6,151,000 | +3.4% | 7,134,877 (+1.2%) |
| 2025 | 6.08–6.16M | −1.1% to +0.1% | – (value-based; certified Aug 27, 2026; unreliable) |

Claims / owner-occupied units: ~86% (2018), ~81% (2021, ACS reweighted to 2020 census), 83% (2022),
84% (2023), 86% (2024).

Large counties (county portions of all school districts; 2021 inferred, 2022–2024 exact, 2025 from
the $15k step): Harris 795,575 → 814,775 → 822,714 → 850,527 → 857,230; Dallas 400,080 → 398,570 →
408,433 → 411,710 → 410,931; Travis 227,261 → 240,028 → 256,571 → 259,631 → 258,640; Bexar 359,947
→ 375,497 → 393,116 → 412,004 → 416,845; Tarrant 386,594 → 400,577 → 405,675 → 412,475 → 373,281
(2025 suspect). HCAD 2023 Annual Report: 163,262 homestead applications in 2023, a "surge" from
legislative changes (https://hcad.org/assets/uploads/pdf/resources/2024/Annual-Report-2023.pdf).

## Reading
- 2022: +5.3% vs a +1.5–1.9% trend (~150–170k above trend), mostly SB 8 and the series break; the
  May 2022 vote came after the April 30 filing deadline.
- 2023: +3.3% (~1.5 points above owner-unit growth); the $100k came after rolls were certified.
- 2024: +3.4% vs +1.2% owner-unit growth (~2 points, ~120k claims) — first year the $100k was known
  before filing; consistent with a modest response (~3–4% of ~1M non-claiming owner units) to a
  ~$600–680/yr gain.
- 2025: no visible jump; data unreliable.
- No published elasticity of take-up to benefit size found. Related: Ihlanfeldt (2021), NTJ 74(2),
  doi:10.1086/714168 (Florida non-claimers); Ihlanfeldt & Rodgers (2022), NTJ
  (https://www.journals.uchicago.edu/doi/10.1086/717587); CMAP Cook County brief (2023); Poverty
  Solutions, Detroit (2018).

## Use in the Florida model
Texas 2024 implies ~4–5.5% of possibly-eligible non-claimers claim at a ~$600 gain, i.e. ~16–21% at
$2,500 under p = 1 − exp(−k·gain).
