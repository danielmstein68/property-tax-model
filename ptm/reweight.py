"""Reweight PUMS households to account for homes built after the survey.

PUMS (survey year) misses households in homes finished afterwards. We count new homes in the
base-year parcel roll by PUMA and raise the weights of PUMS households in recently built homes
in the same PUMA (and same tenure) to cover the gap. They're real respondents in new homes
nearby, so distributions stay realistic (see CHALLENGES: aggregates vs distributions).

Owners: target = homestead parcels built in [survey year, base year - 1].
Renters: target = units in multi-family parcels (DOR use 003, 008) built in those years x an
         occupancy rate (new buildings are still leasing up). Single-family rentals can't be told
         apart from second homes in the roll, so they're left out.
Gap = target - PUMS households (same tenure, same PUMA) already in homes built in the survey year.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import fl_dor_to_fips, fl_parcel_puma, puma_main_county

ROOT = Path(__file__).resolve().parents[1]
REPLICATES = [f"WGTP{i}" for i in range(1, 81)]


def new_home_targets(base_year: int, survey_year: int, occupancy: float = 0.9) -> pd.DataFrame:
    """New owner households and occupied rental units by PUMA, from the base-year roll."""
    cols = ["CO_NO", "CENSUS_BK", "DOR_UC", "ACT_YR_BLT", "homestead", "NO_RES_UNTS"]
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    p = pd.concat([pd.read_parquet(f, columns=cols) for f in files])
    p = p[p["ACT_YR_BLT"].between(survey_year, base_year - 1)]
    p["owner"] = p["homestead"].astype(float)
    p["renter"] = np.where(p["DOR_UC"].isin(["003", "008"]), p["NO_RES_UNTS"].fillna(0) * occupancy, 0.0)
    p["PUMA"] = fl_parcel_puma(p)
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])

    matched = p[p["PUMA"].notna()].groupby(["county_fips", "PUMA"])[["owner", "renter"]].sum()
    unmatched = p[p["PUMA"].isna()].groupby("county_fips")[["owner", "renter"]].sum()

    # Spread unmatched parcels over the county's PUMAs, in proportion to matched new homes
    # (or equally if the county has none matched).
    pm = puma_main_county("12")
    out = matched.reset_index()
    extra = []
    for fips, row in unmatched.iterrows():
        pumas = pm.loc[pm["county_fips"] == fips, "PUMA"].tolist()
        m = matched.loc[fips] if fips in matched.index.get_level_values(0) else None
        for col in ["owner", "renter"]:
            if m is not None and m[col].sum() > 0:
                share = m[col] / m[col].sum()
            else:
                share = pd.Series(1 / len(pumas), index=pumas) if pumas else pd.Series(dtype=float)
            for puma, s in share.items():
                extra.append({"county_fips": fips, "PUMA": puma, col: row[col] * s})
    out = pd.concat([out, pd.DataFrame(extra)]).fillna(0)
    return out.groupby("PUMA")[["owner", "renter"]].sum().reset_index()


def reweight_new_development(households: pd.DataFrame, targets: pd.DataFrame, survey_year: int,
                             min_donors: int = 10, max_multiplier: float = 4.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raise weights of PUMS households in recently built homes to cover new homes.

    Donors: same tenure (owner / renter), YRBLT >= 2020, same PUMA. If a PUMA has fewer than
    `min_donors` donor records or would need a multiplier above `max_multiplier`, its gap is
    pooled with the rest of its county and spread over the county's donors. Multipliers are
    capped at `max_multiplier`; any gap left over is reported, not forced.
    The household weight and all 80 replicate weights are scaled by the same multiplier.
    Returns (households with WGTP updated and new_dev_multiplier, report by PUMA and tenure).
    """
    h = households.copy()
    h["PUMA"] = h["PUMA"].astype(str).str.zfill(5)
    cty = puma_main_county("12").set_index("PUMA")["county_fips"]
    h["county_fips_main"] = h["PUMA"].map(cty)
    h["new_dev_multiplier"] = 1.0
    report = []

    for tenure, col in [("owner", "owner"), ("renter", "renter")]:
        is_t = h["tenure"] == tenure
        donor = is_t & (h["YRBLT"] >= 2020)
        have = h[is_t & (h["YRBLT"] == survey_year)].groupby("PUMA")["WGTP"].sum()
        tgt = targets.set_index("PUMA")[col]
        gap = (tgt - have.reindex(tgt.index).fillna(0)).clip(lower=0)

        dw = h[donor].groupby("PUMA")["WGTP"].sum()
        dn = h[donor].groupby("PUMA").size()
        pooled = {}
        for puma, g in gap.items():
            if g <= 0:
                continue
            ok = dn.get(puma, 0) >= min_donors and 1 + g / dw.get(puma, np.inf) <= max_multiplier
            if ok:
                m = 1 + g / dw[puma]
                h.loc[donor & (h["PUMA"] == puma), "new_dev_multiplier"] = m
                report.append((tenure, puma, cty.get(puma), g, dn.get(puma, 0), m, 0.0, "puma"))
            else:
                pooled[cty.get(puma)] = pooled.get(cty.get(puma), 0) + g
                report.append((tenure, puma, cty.get(puma), g, dn.get(puma, 0), np.nan, 0.0, "pooled to county"))
        for fips, g in pooled.items():
            # county donors not already used at PUMA level
            sel = donor & (h["county_fips_main"] == fips) & (h["new_dev_multiplier"] == 1.0)
            w = h.loc[sel, "WGTP"].sum()
            if w == 0:
                report.append((tenure, None, fips, g, 0, np.nan, g, "no donors in county"))
                continue
            m = min(1 + g / w, max_multiplier)
            h.loc[sel, "new_dev_multiplier"] = m
            left = max(g - (m - 1) * w, 0)
            report.append((tenure, None, fips, g, int(sel.sum()), m, left, "county pool"))

    for c in ["WGTP"] + REPLICATES:
        h[c] = h[c] * h["new_dev_multiplier"]
    rep = pd.DataFrame(report, columns=["tenure", "PUMA", "county_fips", "gap", "donor_records",
                                        "multiplier", "unallocated", "level"])
    return h.drop(columns="county_fips_main"), rep
