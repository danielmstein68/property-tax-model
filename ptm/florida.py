"""Florida property tax rules (current law), as plain functions.

Start of the rules module: Save Our Homes and the homestead exemption. More rules
(non-homestead 10% cap, other exemptions, Amendment 3 settings) will be added here.
"""

import numpy as np
import pandas as pd

# Homestead exemption (s. 196.031 F.S.):
#   first $25,000 of assessed value: exempt from all levies (school and non-school);
#   second band: exempt from non-school levies only, on assessed value between $50,000 and
#   $50,000 + SECOND_EXEMPTION[year]. Indexed for inflation from 2025.
FIRST_EXEMPTION = 25_000
SECOND_EXEMPTION = {2024: 25_000, 2025: 25_722, 2026: 26_411}  # 2026: FL DOR cpi_homestead_exemption.pdf


def soh_assessed(prev_assessed, just_value, cap):
    """Save Our Homes: assessed value grows by at most `cap`, and never exceeds just value."""
    return np.minimum(np.asarray(prev_assessed) * (1 + cap), np.asarray(just_value))


def homestead_taxable(assessed, year: int) -> tuple[np.ndarray, np.ndarray]:
    """School and non-school taxable value of a homestead after the homestead exemption."""
    av = np.asarray(assessed, dtype=float)
    school = np.maximum(av - FIRST_EXEMPTION, 0)
    second = np.clip(av - 50_000, 0, SECOND_EXEMPTION[year])
    nonschool = np.maximum(av - FIRST_EXEMPTION - second, 0)
    return school, nonschool


def soh_ratio_from_purchase(purchase_year, base_year: int, history: pd.DataFrame) -> np.ndarray:
    """Assessed / just value in `base_year` for a homestead bought in `purchase_year`.

    Assessed value starts at just value in the purchase year (the cap resets on sale), then
    grows by each year's Save Our Homes cap; just value follows the price index. The ratio is
    capped at 1. `history` has columns year, soh_cap, hpi (inputs/fl_soh_history.csv).
    Ignores portability (movers carrying up to $500k of savings) and hurricane/rebuild resets.
    """
    h = history.set_index("year")
    caps = h["soh_cap"].fillna(0)
    cum_cap = (1 + caps).cumprod()
    hpi = h["hpi"]
    py = np.clip(np.asarray(purchase_year, dtype=int), h.index.min(), base_year)
    assessed_growth = cum_cap.loc[base_year] / cum_cap.reindex(py).to_numpy()
    value_growth = hpi.loc[base_year] / hpi.reindex(py).to_numpy()
    return np.minimum(assessed_growth / value_growth, 1.0)
