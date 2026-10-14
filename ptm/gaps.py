"""Assessment gaps from the parcel roll: assessed / just value for each owner household.

The roll has every parcel's school and non-school assessed value (AV_SD, AV_NSD) and just
value (JV), but not how long the owner has had it. PUMS has move-in year (MV) but no assessed
value. We combine them: within each county group x home type x value band, PUMS households are
ordered by our move-in-year estimate of their gap (soh_ratio_<base>, from
add_aged_taxamt_rules) and given the roll's actual ratios in the same order. So:
  - each cell's gap distribution is the roll's real one (fixes the weak county pattern of the
    move-in-year estimate: correlation 0.40 with the roll by county);
  - long-time owners still get the deepest gaps, recent buyers the shallowest.
Homesteads draw from roll homesteads (Save Our Homes); non-claimers from roll non-homesteads
(10% cap on non-school levies only; school assessed value = just value). School and non-school
ratios come from the same donor parcel, so they stay consistent.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import county_groups, fl_dor_to_fips, parcel_area
from ptm.link import ROLL_HOME_TYPE

ROOT = Path(__file__).resolve().parents[1]
BANDS = ["low", "mid", "high"]


def quantile_pick(scores: np.ndarray, weights: np.ndarray, n_tail: int) -> np.ndarray:
    """Index into a sorted tail of length n_tail for each household, by weighted-midpoint
    position in score order (like ptm.topcode.quantile_map, but returns donor positions so
    several of the donor's fields can be carried over together)."""
    order = np.argsort(scores, kind="stable")
    cum = np.cumsum(weights[order])
    q = (cum - weights[order] / 2) / cum[-1]
    idx = np.empty(len(scores), dtype=int)
    idx[order] = np.minimum((q * n_tail).astype(int), n_tail - 1)
    return idx


def _bands(values: pd.Series, weights: pd.Series | None = None) -> pd.Series:
    """Value thirds (weighted if weights given)."""
    order = values.sort_values(kind="stable").index
    w = weights.loc[order] if weights is not None else pd.Series(1.0, index=order)
    cum = w.cumsum() / w.sum()
    return pd.cut(cum, [0, 1 / 3, 2 / 3, 1.0001], labels=BANDS).astype(str).reindex(values.index)


def roll_ratios(base_year: int) -> pd.DataFrame:
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    cols = ["CO_NO", "CENSUS_BK", "DOR_UC", "JV", "AV_SD", "AV_NSD", "homestead"]
    r = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    r["type"] = r["DOR_UC"].map(ROLL_HOME_TYPE)
    r = r[r["type"].notna() & (r["JV"] > 0) & r["AV_SD"].notna() & r["AV_NSD"].notna()]
    r["r_sd"] = (r["AV_SD"] / r["JV"]).clip(upper=1)
    r["r_nsd"] = (r["AV_NSD"] / r["JV"]).clip(upper=1)
    r["area"] = parcel_area(r)
    pct = r.groupby(["area", "type", "homestead"])["JV"].rank(pct=True, method="first")
    r["band"] = pd.cut(pct, [0, 1 / 3, 2 / 3, 1.0001], labels=BANDS).astype(str)
    return r[["area", "type", "homestead", "band", "JV", "r_sd", "r_nsd"]]


def tax_implied_ratio(o: pd.DataFrame, base_year: int) -> pd.Series:
    """Assessed/just ratio implied by a homestead's reported (aged) tax.

    tax ~ rate x (school share x (AV - 25k) + non-school share x (AV - 25k - second exemption)),
    so AV ~ tax / rate + effective exemption. `rate` = the area's typical rate: weighted median of
    taxamt_aged / modelled taxable value (move-in-year gaps) among homesteads with usable tax.
    NaN for $0 or top-coded tax.
    """
    from ptm import florida
    from ptm.aging import SCHOOL_SHARE

    exempt = SCHOOL_SHARE * florida.FIRST_EXEMPTION + (1 - SCHOOL_SHARE) * (
        florida.FIRST_EXEMPTION + florida.SECOND_EXEMPTION[base_year])
    av_model = o[f"soh_ratio_{base_year}"].fillna(1.0) * o["valp_jv_cal"]
    taxable_model = (av_model - exempt).clip(lower=1)
    usable = (o["TAXAMT"] > 0) & ~o["flag_topcode_taxamt"] & o["is_hs"]
    rate = (o["taxamt_aged"] / taxable_model).where(usable)

    def wmed(g):
        g = g.dropna()
        if g.empty:
            return np.nan
        v, w = g["rate"].to_numpy(), g["WGTP"].to_numpy()
        i = np.argsort(v)
        c = np.cumsum(w[i])
        return v[i][np.searchsorted(c, c[-1] / 2)]

    typical = pd.DataFrame({"rate": rate, "WGTP": o["WGTP"], "area": o["value_area"]}).groupby("area").apply(wmed)
    av_tax = o["taxamt_aged"] / o["value_area"].map(typical) + exempt
    return (av_tax / o["valp_jv_cal"]).clip(0, 1).where(usable)


def assign_assessment_gaps(h: pd.DataFrame, base_year: int, seed: int = 2026, min_pums: int = 20,
                           min_roll: int = 200, tax_weight: float = 1.0,
                           recent_tax_weight: float | None = 0.2,
                           tax_rank_value_groups: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Give each owner (not rented-lot mobile homes) school and non-school assessed/just ratios.

    Requires calibrate_values (value_area, valp_jv_cal) and add_aged_taxamt_rules
    (soh_ratio_<base>). Cells: value_area x home_type x value band (thirds of calibrated just
    value, by homestead status). Fallback when a cell is thin (< min_pums PUMS records or
    < min_roll roll parcels): area x type, then statewide type.
    Ordering: homesteads by a blend (tax_weight) of the move-in-year gap estimate and the gap
    implied by their reported tax (tax_implied_ratio) — deepest first; move-in estimate alone where
    tax is $0 or top-coded. Move-in alone left the gaps random within each move-in category and
    explained reported tax slightly worse than before. Non-claimers by move-in category (longest first; the 10% non-school cap only builds a gap
    over time), ties at random.
    Adds av_ratio_sd, av_ratio_nsd, av_sd_<base>, av_nsd_<base> (= ratio x valp_jv_cal), gap_level.
    Returns (households, report by area x type x homestead).
    """
    out = h.copy()
    rng = np.random.default_rng(seed)
    roll = roll_ratios(base_year)
    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)
    o = out[owner].copy()
    o["is_hs"] = (o["homestead"] == True).to_numpy()  # noqa: E712
    o["band"] = ""
    for _, idx in o.groupby(["value_area", "home_type", "is_hs"]).groups.items():
        o.loc[idx, "band"] = _bands(o.loc[idx, "valp_jv_cal"], o.loc[idx, "WGTP"])
    # Homesteads: blend of percentile ranks (within area) of the move-in-year gap estimate and the
    # gap implied by reported tax (tax_weight); model only where tax isn't usable.
    jitter = rng.random(len(o)) * 1e-6
    model_rank = (o[f"soh_ratio_{base_year}"].fillna(1.0) + jitter).groupby(o["value_area"]).rank(pct=True)
    tax_ratio = tax_implied_ratio(o, base_year)
    # Rank the tax-implied gap only against homes of similar value (value_groups within each donor
    # cell): high-value owners report low tax relative to their calibrated value, so ranking
    # across the whole cell gave $2M+ homes the deepest gaps (assessed/just 0.53 vs roll 0.64).
    if tax_rank_value_groups and tax_rank_value_groups > 1:
        o["_vg"] = 0
        for _, idx in o.groupby(["value_area", "home_type", "is_hs", "band"]).groups.items():
            v = o.loc[idx, "valp_jv_cal"]
            order = v.sort_values(kind="stable").index
            cum = o.loc[order, "WGTP"].cumsum() / o.loc[order, "WGTP"].sum()
            o.loc[order, "_vg"] = np.minimum((cum.to_numpy() * tax_rank_value_groups).astype(int), tax_rank_value_groups - 1)
        tax_rank = (tax_ratio + jitter).groupby([o["value_area"], o["home_type"], o["is_hs"], o["band"], o["_vg"]]).rank(pct=True)
    else:
        tax_rank = (tax_ratio + jitter).groupby(o["value_area"]).rank(pct=True)
    # Recent movers (MV 1-3: moved in under 5 years before the survey) can use their own weight:
    # their reported tax is often the previous owner's capped bill, not their reset assessment.
    tw = np.where(o["MV"].fillna(4) <= 3, tax_weight if recent_tax_weight is None else recent_tax_weight, tax_weight)
    hs_order = np.where(tax_rank.notna(), (1 - tw) * model_rank + tw * tax_rank, model_rank)
    o["_order"] = np.where(o["is_hs"], hs_order, -o["MV"].fillna(4) + jitter)

    groups = {k: g for k, g in roll.groupby(["area", "type", "homestead", "band"])}
    groups_at = {k: g for k, g in roll.groupby(["area", "type", "homestead"])}
    groups_st = {k: g for k, g in roll.groupby(["type", "homestead"])}

    res = pd.DataFrame(index=o.index, columns=["av_ratio_sd", "av_ratio_nsd", "gap_level"])
    report = []
    for key, idx in o.groupby(["value_area", "home_type", "is_hs", "band"]).groups.items():
        area, typ, is_hs, band = key
        g = o.loc[idx]
        tail = groups.get((area, typ, is_hs, band))
        level = "area x type x band"
        if tail is None or len(tail) < min_roll or len(g) < min_pums:
            tail, level = groups_at.get((area, typ, is_hs)), "area x type"
        if tail is None or len(tail) < min_roll:
            tail, level = groups_st[(typ, is_hs)], "statewide type"
        tail = tail.sort_values(["r_sd", "r_nsd"], kind="stable")
        sort_key = "r_sd" if is_hs else "r_nsd"
        tail = tail.sort_values(sort_key, kind="stable")
        pos = quantile_pick(g["_order"].to_numpy(), g["WGTP"].to_numpy(), len(tail))
        res.loc[idx, "av_ratio_sd"] = tail["r_sd"].to_numpy()[pos]
        res.loc[idx, "av_ratio_nsd"] = tail["r_nsd"].to_numpy()[pos]
        res.loc[idx, "gap_level"] = level
        report.append({"area": area, "type": typ, "homestead": is_hs, "band": band, "level": level,
                       "pums_records": len(g), "donor_parcels": len(tail),
                       "roll_median_r_sd": tail["r_sd"].median(),
                       "assigned_wmedian_r_sd": np.average(res.loc[idx, "av_ratio_sd"].astype(float), weights=g["WGTP"])})

    for c in ["av_ratio_sd", "av_ratio_nsd"]:
        out.loc[res.index, c] = res[c].astype(float)
    out.loc[res.index, "gap_level"] = res["gap_level"]
    out[f"av_sd_{base_year}"] = out["av_ratio_sd"] * out["valp_jv_cal"]
    out[f"av_nsd_{base_year}"] = out["av_ratio_nsd"] * out["valp_jv_cal"]
    return out, pd.DataFrame(report)
