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

## Second pass: the 5% cap piece from the rolls (2026-10-23, `scripts/check_a3_cap_static.py`, `scripts/fl_nonres_2026.py`)
Non-homestead, non-agricultural parcels (residential from the processed rolls, commercial/industrial/other from the raw
zips), assessed value growing at the lower of just-value growth and the cap (10% vs 5%), no sales, 2025 rates. Just-value
growth is the state's forecast less new construction (new construction enters at just value, outside the cap). Using the
state's growth with new construction left in overstated the cap piece ($2.0B in 2031); that was a mistake in my first run.

| Roll year | 2027 | 2028 | 2029 | 2030 | 2031 |
|---|---|---|---|---|---|
| Cap piece, rolls only | 0.25 | 0.42 | 0.56 | 0.68 | 0.80 |
| Cap piece, model (`a3_cap`) | 0.25 | 0.41 | 0.52 | 0.62 | 0.71 |
| Homestead piece, rolls only (above) | 4.31 | 7.33 | 7.55 | 7.78 | 8.02 |
| Rolls-only total | 4.56 | 7.75 | 8.11 | 8.46 | 8.82 |
| Model total | 4.56 | 7.80 | 8.18 | 8.54 | 9.02 |
| State | 4.93 | 8.71 | 9.65 | 10.71 | 11.83 |

Both pieces reproduce from the rolls (model total vs rolls-only: 0.6% to 2.3% apart by year). The whole gap to the state is therefore
in what the state adds: its scaling to its taxable value forecast (homestead factor 1.04 to 1.18) plus a remainder of
~5-10% not explained by anything published. The state's workpapers (adjustable offset, scale factors, cap piece) would settle it.
