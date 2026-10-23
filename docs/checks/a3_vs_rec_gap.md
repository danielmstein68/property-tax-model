# Check: why the model's Amendment 3 loss falls below the state's, more each year (2026-10-23)

Script: `scripts/check_a3_roll_static.py` (2026 rolls, all 5.2M homestead parcels, 2025 non-school rates).
State: impact0710.pdf (Revenue Estimating Conference, July 10, 2026), cash by roll year.

| Roll year | State | Model | Gap | Roll-only homestead loss (state's method, no scaling) | Same, scaled to state's taxable value forecast | Model x same scale |
|---|---|---|---|---|---|---|
| 2027 | 4.93 | 4.56 | -7% | 4.31 | 4.50 | 4.76 (-3%) |
| 2028 | 8.71 | 7.80 | -10% | 7.33 | 7.88 | 8.38 (-4%) |
| 2029 | 9.65 | 8.18 | -15% | 7.55 | 8.38 | 9.08 (-6%) |
| 2030 | 10.71 | 8.54 | -20% | 7.78 | 8.89 | 9.76 (-9%) |
| 2031 | 11.83 | 9.02 | -24% | 8.02 | 9.45 | 10.63 (-10%) |

$ billions. Roll-only: each parcel's assessed value grows at the lower of just-value growth (state's homestead
forecast less 1.15% new construction) and a 2.8% Save Our Homes cap, no sales.

## Findings
- The model's homestead-exemption piece reproduces from the rolls alone ($4.31B in 2027 both ways; 2031 $8.0B roll-only
  with 1.067 more homesteads = $8.6B vs model $8.3B after its newcomer offset).
- The state scales its loss each year by (its homestead taxable forecast / its parcel-only baseline). That factor is
  1.04 in 2027 and 1.18 by 2031. It treats all value growth beyond the Save Our Homes cap (sales resets, new
  construction, switching) as more homesteads. Real homestead counts grow ~1.3% a year (model: 6.7% by 2031).
  Sales resets raise assessed value on parcels already counted, which barely changes the loss once assessed value
  is above the exemption. So the scaling probably overstates later years; the model's bottom-up path doesn't use it.
- Applying the state's scale to the model closes 24% to 10% in 2031. What's left (3-10%) is not explained: the state's
  5% cap piece is unpublished; the state's newcomer offset (~$0.1B 2028, ~$0.5B 2031) would widen it slightly.
- Not the cause: rate path (model rates fall ~1% by 2031), homestead universe (all use codes: same), exemption amounts.
