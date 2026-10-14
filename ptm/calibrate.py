"""Calibrate PUMS values to the base-year parcel roll.

Values: after aging, PUMS just values run ~4% below the roll statewide and 10-24% below in South
Florida. We match percentiles (quantile mapping) rather than adjust weights: weights already
match homestead and new-home counts, and reweighting would distort other distributions. Each
household keeps its rank; only value levels move. VALP stays as the observed anchor.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import county_groups, fl_dor_to_fips, parcel_area
from ptm.link import ROLL_HOME_TYPE
from ptm.topcode import quantile_map

ROOT = Path(__file__).resolve().parents[1]


def calibrate_values(h: pd.DataFrame, base_year: int, min_pums: int = 30,
                     min_roll: int = 200) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match homesteads' just values to the roll's homestead distribution by area x home type.

    Areas: county groups (ptm.geo.county_groups) so PUMS PUMAs and roll counties line up.
    Homesteads (homestead True) in each area x type (sfr, condo, mobile on own land) are
    quantile-mapped onto the roll's homestead just values for that area x type, ordered by
    their aged just value (valp_jv_aged; top-coded households already carry draws from the
    roll's top tail, so they keep their order and get the area's actual top values).
    Non-claimers get the homesteads' calibration ratio at the same value position in their
    area x type (interpolated; flat beyond the ends). Rented-lot mobile homes aren't real
    property and are left as is.
    Thin cells (fewer than min_pums homestead records or min_roll roll homesteads) use one
    ratio: roll median / PUMS weighted median for that type statewide.

    Adds value_area, valp_jv_cal (base-year just value), valp_market_cal (= valp_jv_cal /
    jv_to_market), value_cal_factor (= valp_jv_cal / valp_jv_aged).
    Returns (households, report by area x type).
    """
    out = h.copy()
    groups = county_groups()
    out["value_area"] = out["PUMA"].astype(str).str.zfill(5).map(groups.drop_duplicates("PUMA").set_index("PUMA")["area"])

    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    roll = pd.concat([pd.read_parquet(f, columns=["CO_NO", "CENSUS_BK", "DOR_UC", "JV", "homestead"]) for f in files])
    roll = roll[roll["homestead"] & (roll["JV"] > 0)]
    roll["type"] = roll["DOR_UC"].map(ROLL_HOME_TYPE)
    roll = roll[roll["type"].notna()]
    roll["area"] = parcel_area(roll)

    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)
    hs = owner & (out["homestead"] == True)  # noqa: E712 (nullable boolean)
    nc = owner & (out["homestead"] == False)  # noqa: E712

    def wmedian(v, w):
        o = np.argsort(v)
        c = np.cumsum(w[o])
        return v[o][np.searchsorted(c, c[-1] / 2)]

    state_ratio = {}
    for t in ["sfr", "condo", "mobile"]:
        s = out[hs & (out["home_type"] == t)]
        state_ratio[t] = roll.loc[roll["type"] == t, "JV"].median() / wmedian(s["valp_jv_aged"].to_numpy(), s["WGTP"].to_numpy())

    out["valp_jv_cal"] = np.nan
    rows = []
    for (area, t), idx in out[owner].groupby(["value_area", "home_type"]).groups.items():
        g = out.loc[idx]
        gh = g[g["homestead"] == True]  # noqa: E712
        tail = roll.loc[(roll["area"] == area) & (roll["type"] == t), "JV"].to_numpy()
        if len(gh) >= min_pums and len(tail) >= min_roll:
            cal = quantile_map(gh["valp_jv_aged"].to_numpy(), gh["WGTP"].to_numpy(), tail)
            out.loc[gh.index, "valp_jv_cal"] = cal
            # Non-claimers: homesteads' ratio at the same value position
            order = np.argsort(gh["valp_jv_aged"].to_numpy())
            x = gh["valp_jv_aged"].to_numpy()[order]
            r = (cal / gh["valp_jv_aged"].to_numpy())[order]
            gn = g[g["homestead"] == False]  # noqa: E712
            out.loc[gn.index, "valp_jv_cal"] = gn["valp_jv_aged"].to_numpy() * np.interp(gn["valp_jv_aged"].to_numpy(), x, r)
            level = "quantile map"
        else:
            out.loc[idx, "valp_jv_cal"] = g["valp_jv_aged"] * state_ratio[t]
            level = "statewide ratio"
        c = out.loc[gh.index]
        rows.append({"area": area, "type": t, "level": level, "pums_homestead_records": len(gh),
                     "pums_homesteads": gh["WGTP"].sum(), "roll_homesteads": len(tail),
                     "pums_median_before": wmedian(gh["valp_jv_aged"].to_numpy(), gh["WGTP"].to_numpy()) if len(gh) else np.nan,
                     "pums_median_after": wmedian(c["valp_jv_cal"].to_numpy(), c["WGTP"].to_numpy()) if len(gh) else np.nan,
                     "roll_median": np.median(tail) if len(tail) else np.nan,
                     "pums_total_after": (c["valp_jv_cal"] * c["WGTP"]).sum(), "roll_total": tail.sum()})

    out["valp_market_cal"] = out["valp_jv_cal"] / out["jv_to_market"]
    out["value_cal_factor"] = out["valp_jv_cal"] / out["valp_jv_aged"]
    return out, pd.DataFrame(rows)
