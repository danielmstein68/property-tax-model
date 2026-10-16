# Check: projected tax bases vs the Ad Valorem Estimating Conference (2026-10-16)

Current-law central projection (history rate rule) vs the Revenue Estimating Conference's adopted
("New") Ad Valorem forecast of July 31 / Aug 3, 2026
(`data/raw/fl_rec_advalorem/2026-08/adval_comparisonstatewidecategories.txt`). Totals include
tangible personal property and centrally assessed property.

## Starting point (2026)
School taxable value $3,965B (REC $3,966B); county (non-school) $3,673B (REC $3,673B). The split by
category differs (the model's non-homestead residential is all residential parcels without a
homestead from the rolls; non-residential = Data Book total minus residential), but totals match.

## Growth
| Year | School: model | School: REC | Level gap | County: model | County: REC | Level gap |
|---|---|---|---|---|---|---|
| 2027 | 5.16% | 4.47% | +0.6% | 7.09% | 4.87% | +2.1% |
| 2028 | 5.68% | 5.33% | +1.0% | 7.21% | 5.69% | +3.6% |
| 2029 | 6.23% | 6.02% | +1.2% | 7.22% | 6.36% | +4.4% |
| 2030 | 6.56% | 6.28% | +1.4% | 7.03% | 6.58% | +4.9% |
| 2031 | 6.76% | 6.43% | +1.8% | 7.05% | 6.69% | +5.2% |

By category (county taxable, real property; model non-residential includes TPP):
| | Homestead | Non-homestead residential | Non-residential |
|---|---|---|---|
| 2027 model / REC | 7.11% / 5.69% | 6.63% / 3.24% | 7.80% / 6.13% |
| 2028 model / REC | 6.11% / 6.14% | 7.62% / 4.78% | 8.03% / 6.66% |
| 2027 school, model / REC | 6.80% / 5.70% | 3.72% / 2.51% | 5.16% / 5.51% |

## Reading
- School bases are close (non-homestead and non-residential school value is just value, so it
  follows the value forecast the model takes from REC).
- Non-school (county) bases grow too fast, mostly non-homestead residential and non-residential:
  the gap between county and school growth is ~2.9 points (nh) in the model vs ~0.7 in REC. The
  cause is the cap-block approximation (`ptm/rate_setting.py`, 2026-10-16): each county's capped
  parcels are one block whose assessed value rises 10% a year until it reaches the block's just
  value. Real gaps are uneven, and REC expects county differentials to fall only 2.1% in 2027.
- Homestead taxable grows ~1.4 points faster than REC in 2027 only (2028 matches); not yet explained
  (candidates: new-owner cohorts at full value, first-year indexing of the second exemption, value
  growth of the model's homesteads vs REC's category forecast).

## Effects
Faster non-school bases mean, under current law: lower history-mode rate increases, a higher
estimate of tax on non-owner property, and a slightly different baseline for revenue-neutral rates.
Policy-vs-current-law differences are less affected (both runs share the bases), but the 5% cap's
effect depends on how fast capped values catch up.

## Fix (proposed, not done)
1. Split each county's cap blocks by depth of gap (assessed / just value bands, e.g. <50%, 50-70%,
   70-80%, 80-90%, 90-97%, at just value) from the 2026 parcels (`scripts/fl_cap_blocks_2026.py`);
   each band catches up separately. Re-check against REC's county differentials.
2. Look into homestead growth in 2027.
Then re-run the grid.
