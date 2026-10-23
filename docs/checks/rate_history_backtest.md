# Check: the rate-setting rule against Florida's history (2026-10-23)

`scripts/check_rate_history_backtest.py`. For each year from 2006, the rule is fitted on earlier years only and predicts
every county, city and school-RLE rate change that year. A well-calibrated rule puts 50% of actual changes inside its
central 50% band and 80% inside the 80% band. MAE = mean absolute error of the predicted median (log points x 100,
about percent); 'hold' and 'rolled-back' are the fixed rules.

## All

| all | n | inside 50% band | inside 80% band | median error (pts) | MAE model | MAE hold | MAE rolled-back |
|---|---|---|---|---|---|---|---|
| all | 8405 | 0.608 | 0.819 | 0 | 2.68 | 2.79 | 7.32 |

## By kind

| kind | n | inside 50% band | inside 80% band | median error (pts) | MAE model | MAE hold | MAE rolled-back |
|---|---|---|---|---|---|---|---|
| county | 1317 | 0.62 | 0.826 | 0 | 2.45 | 2.45 | 7.07 |
| municipal | 5749 | 0.614 | 0.806 | 0 | 2.69 | 2.7 | 7.45 |
| school | 1339 | 0.569 | 0.869 | -0.314 | 2.83 | 3.47 | 7.03 |

## By period

| period | n | inside 50% band | inside 80% band | median error (pts) | MAE model | MAE hold | MAE rolled-back |
|---|---|---|---|---|---|---|---|
| 2006-07 | 265 | 0.438 | 0.679 | -2.15 | 5.71 | 6.52 | 13.8 |
| 2008-12 | 1421 | 0.573 | 0.808 | 0 | 3.2 | 3.17 | 7.27 |
| 2013-19 | 3605 | 0.601 | 0.83 | 0 | 2.46 | 2.59 | 5.58 |
| 2020-25 | 3114 | 0.646 | 0.823 | 0 | 2.43 | 2.51 | 8.8 |

## By base growth that year

| growth | n | inside 50% band | inside 80% band | median error (pts) | MAE model | MAE hold | MAE rolled-back |
|---|---|---|---|---|---|---|---|
| falling >2% | 1798 | 0.564 | 0.791 | 0 | 3.26 | 3.27 | 7.29 |
| -2% to 2% | 1789 | 0.586 | 0.818 | 0 | 2.52 | 2.58 | 3.06 |
| 2% to 6% | 2108 | 0.623 | 0.831 | 0 | 2.04 | 2.19 | 4.43 |
| 6% to 12% | 1599 | 0.634 | 0.824 | 0 | 2.54 | 2.65 | 8.29 |
| over 12% | 1111 | 0.647 | 0.836 | 0 | 3.39 | 3.65 | 18.3 |

## Falling or flat base, by period

| period | growth | n | inside 50% band | inside 80% band | median error (pts) | MAE model | MAE hold | MAE rolled-back |
|---|---|---|---|---|---|---|---|---|
| 2006-07 | falling >2% | 12 | 0.25 | 0.417 | -0.579 | 4.94 | 4.59 | 7.96 |
| 2006-07 | -2% to 2% | 22 | 0.364 | 0.455 | -7.39 | 6.97 | 7.53 | 7.04 |
| 2008-12 | falling >2% | 1165 | 0.583 | 0.812 | 0 | 3.25 | 3.24 | 7.91 |
| 2008-12 | -2% to 2% | 205 | 0.537 | 0.805 | 0 | 2.65 | 2.51 | 2.93 |
| 2013-19 | falling >2% | 491 | 0.534 | 0.77 | 0 | 3.15 | 3.22 | 5.68 |
| 2013-19 | -2% to 2% | 1037 | 0.591 | 0.834 | 0 | 2.48 | 2.62 | 3.12 |
| 2020-25 | falling >2% | 130 | 0.538 | 0.715 | 0 | 3.61 | 3.58 | 7.77 |
| 2020-25 | -2% to 2% | 525 | 0.604 | 0.808 | 0 | 2.35 | 2.33 | 2.82 |

## Reading (2026-10-23)
- Calibration is good: 82% of actual changes fall in the 80% band (nominal 80%), for counties, cities and school districts, and
  in every period after 2007 (2008-12 recession included: 81%). The 50% band holds 61% because about half of county and city
  rates don't change at all (exact zeros count as inside).
- The rule predicts better than "hold the rate" only slightly for counties and cities (error 2.45 vs 2.45 and 2.69 vs 2.70
  points) and clearly for school districts (2.83 vs 3.47). Local governments mostly leave rates alone, and base growth tells
  little about whether they won't. That is what the model's "governments respond" mode encodes.
- 2006-07 is poorly covered (44% / 68%): the 2007 rollback law (SB 1-2007) changed the rules, so rules matter.
- What this does not test: a loss as large and as visible as Amendment 3's. In falling-base years (mostly 2008-12) the rule
  holds up (79% in the 80% band), but those were market declines under different rules. Nothing in Florida's history is an
  exemption-sized, state-imposed loss.
