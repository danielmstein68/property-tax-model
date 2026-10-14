"""Link PUMS households to the parcel roll: tax-relevant facts PUMS doesn't have.

Each step answers one question needed to simulate a household's property tax, using the
base-year parcel roll for counts by PUMA and PUMS signals to pick which households.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import fl_parcel_counts_by_puma

ROOT = Path(__file__).resolve().parents[1]


def _roll(base_year: int, cols: list[str]) -> pd.DataFrame:
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    return pd.concat([pd.read_parquet(f, columns=cols) for f in files])


def _fill_by_priority(h: pd.DataFrame, eligible: pd.Series, target_by_puma: pd.Series,
                      priority: list[str], ascending: list[bool]) -> pd.Series:
    """Mark eligible households, highest priority first within each PUMA, until their weights
    reach the PUMA's target. A household is marked if that brings the total closer to the target."""
    marked = pd.Series(False, index=h.index)
    for puma, idx in h[eligible].groupby("PUMA").groups.items():
        target = target_by_puma.get(puma, 0.0)
        if target <= 0:
            continue
        order = h.loc[idx].sort_values(priority, ascending=ascending).index
        total = 0.0
        for i in order:
            w = h.at[i, "WGTP"]
            if total + w / 2 > target:
                break
            marked[i] = True
            total += w
    return marked


def assign_mobile_home_lots(h: pd.DataFrame, base_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Which mobile-home owners sit on rented lots (no real-estate tax, no homestead)?

    Count per PUMA: PUMS mobile-home owners minus the roll's homestead mobile-home parcels
    (DOR use 002), i.e. owners on their own land. Within a PUMA, pick the households most
    likely to be on a rented lot first: lot under 1 acre, $0 reported tax, highest yearly
    mobile-home costs (MHP includes site rent), lowest value.

    Adds mh_rented_lot (bool). For the tax simulation these owners pay no real-estate tax
    and can't claim homestead; their tax reaches them through lot rent (pass-through, later).
    Returns (households, report by PUMA).
    """
    out = h.copy()
    out["PUMA"] = out["PUMA"].astype(str).str.zfill(5)
    mh = (out["tenure"] == "owner") & (out["home_type"] == "mobile")

    roll = _roll(base_year, ["CO_NO", "CENSUS_BK", "DOR_UC", "homestead"])
    roll["mh_homestead"] = ((roll["DOR_UC"] == "002") & roll["homestead"]).astype(float)
    own_land = fl_parcel_counts_by_puma(roll, ["mh_homestead"]).set_index("PUMA")["mh_homestead"]

    pums_mh = out[mh].groupby("PUMA")["WGTP"].sum()
    target = (pums_mh - own_land.reindex(pums_mh.index).fillna(0)).clip(lower=0)

    out["_big_lot"] = out["ACR"].fillna(1) >= 2
    out["_zero_tax"] = out["TAXAMT"] == 0
    out["mh_rented_lot"] = _fill_by_priority(
        out, mh, target,
        priority=["_big_lot", "_zero_tax", "MHP", "VALP"], ascending=[True, False, False, True])

    report = pd.DataFrame({"pums_mobile_owners": pums_mh, "roll_mh_homesteads": own_land.reindex(pums_mh.index).fillna(0),
                           "target_rented_lot": target,
                           "assigned_rented_lot": out[out["mh_rented_lot"]].groupby("PUMA")["WGTP"].sum()}).fillna(0)
    return out.drop(columns=["_big_lot", "_zero_tax"]), report.reset_index()
