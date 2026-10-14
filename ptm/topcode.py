"""Replace top-coded PUMS home values with values drawn from the parcel roll's real top tail.

PUMS replaces values above a cut-off with one state amount (Florida 2024: $6,471,000). The roll
shows that amount is the *mean* above a ~$3M cut-off (statewide: the top 52,868 homesteads by
market value start at $2.99M and average $6.29M), so totals are roughly right and the spread is
what's missing. With every parcel available we draw from the roll's actual top homesteads
(method B, exact version) rather than fitting a curve. Method A — fitting a Pareto tail to PUMS
homes just below the cut-off — is the fallback for states without parcel data (CHALLENGES.md).

Matching is guided by reported tax: households reporting more tax get the more expensive homes,
with noise, so value and tax stay lined up for effective tax rates at the top.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import fl_dor_to_fips

ROOT = Path(__file__).resolve().parents[1]
ROLL_TYPE = {"001": "sfr", "004": "condo", "005": "condo"}


def quantile_map(scores: np.ndarray, weights: np.ndarray, tail: np.ndarray) -> np.ndarray:
    """Give each household the tail value at its weighted-midpoint position in score order.

    The weighted distribution of the returned values reproduces `tail`'s distribution, and a
    higher score always gets a value at least as high.
    """
    scores, weights = np.asarray(scores, float), np.asarray(weights, float)
    tail = np.sort(np.asarray(tail, float))
    order = np.argsort(scores, kind="stable")
    cum = np.cumsum(weights[order])
    q = (cum - weights[order] / 2) / cum[-1]
    pos = (np.arange(len(tail)) + 0.5) / len(tail)
    out = np.empty(len(scores))
    out[order] = np.interp(q, pos, tail)
    return out


def roll_tail_values(base_year: int) -> pd.DataFrame:
    """Homestead single-family and condo parcels with values on the PUMS basis.

    Returns county_fips, type, jv (base-year just value), market (base-year market value =
    jv / just-to-market ratio) and value_survey (survey-year market value = market / value
    growth factor), using the top-tier cells of the inputs tables.
    """
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    p = pd.concat([pd.read_parquet(f, columns=["CO_NO", "DOR_UC", "JV", "homestead"]) for f in files])
    p = p[p["homestead"] & p["DOR_UC"].isin(ROLL_TYPE) & (p["JV"] > 0)]
    p = pd.DataFrame({"county_fips": fl_dor_to_fips(p["CO_NO"]).to_numpy(),
                      "type": p["DOR_UC"].map(ROLL_TYPE).to_numpy(), "jv": p["JV"].to_numpy()})

    jvr = pd.read_csv(ROOT / "inputs" / f"just_value_ratio_fl_{base_year}.csv", dtype={"county_fips": str})
    growth = pd.read_csv(ROOT / "inputs" / f"value_growth_fl_{base_year}.csv", dtype={"county_fips": str})
    jvr = jvr[jvr["tier"] == "top"].set_index(["county_fips", "type"])["jv_to_market"]
    growth = growth[growth["tier"] == "top"].set_index(["county_fips", "type"])["factor"]
    key = pd.MultiIndex.from_frame(p[["county_fips", "type"]])
    p["market"] = p["jv"] / jvr.reindex(key).to_numpy()
    p["value_survey"] = p["market"] / growth.reindex(key).to_numpy()
    return p.dropna(subset=["value_survey"])


def impute_topcoded_values(h: pd.DataFrame, base_year: int, noise: float = 0.25, seed: int = 2026,
                           min_records: int = 20, min_tail: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replace top-coded owner values (flag_topcode_valp) with draws from the roll's top tail.

    Requires add_aged_values (county_fips, valp_market_aged, valp_jv_aged).
    Cut-off: PUMS top-codes above one statewide amount, so the cut-off is statewide — the value of
    the N-th most valuable roll homestead statewide (survey-year market value), N = weighted
    top-coded households statewide (Florida 2024: ~$3.09M).
    Regions: counties with >= min_records top-coded records and >= min_tail roll homesteads above
    the cut-off; the rest pooled as 'rest'. Each region's tail = its roll homesteads (single-family
    and condo) above the cut-off. Where PUMS has more (or fewer) top-coded households than the roll
    has such homes (e.g. Brevard 2,088 vs 252), values still come from that region's real tail;
    the count mismatch is left to value calibration.
    Households are ordered by score = percentile rank of reported TAXAMT (ties broken at random)
    + normal noise (sd `noise`), then quantile-mapped onto the tail.

    Adds valp_2024 (VALP, or the imputed survey-year market value), topcode_region,
    topcode_cutoff (the region tail's minimum); overwrites valp_market_aged and valp_jv_aged
    for top-coded records, keeping each one's own type/tier ratios consistent. VALP is untouched.
    Returns (households, report by region).
    """
    out = h.copy()
    out["valp_2024"] = out["VALP"]
    tc = out["flag_topcode_valp"].fillna(False).astype(bool) & (out["tenure"] == "owner")
    if not tc.any():
        return out, pd.DataFrame()

    roll = roll_tail_values(base_year)
    n_state = int(round(out.loc[tc, "WGTP"].sum()))
    cutoff = roll["value_survey"].nlargest(n_state).min()
    above = roll[roll["value_survey"] >= cutoff].copy()

    counts = out[tc].groupby("county_fips").size()
    tail_counts = above.groupby("county_fips").size()
    big = {c for c in counts[counts >= min_records].index if tail_counts.get(c, 0) >= min_tail}
    out.loc[tc, "topcode_region"] = out.loc[tc, "county_fips"].where(out.loc[tc, "county_fips"].isin(big), "rest")
    above["region"] = above["county_fips"].where(above["county_fips"].isin(big), "rest")
    rng = np.random.default_rng(seed)

    rows = []
    for region, idx in out[tc].groupby("topcode_region").groups.items():
        g = out.loc[idx]
        tail = above.loc[above["region"] == region, ["value_survey", "market", "jv"]]

        rank = (g["TAXAMT"].fillna(0) + rng.random(len(g)) * 1e-6).rank(pct=True).to_numpy()
        score = rank + rng.normal(0, noise, len(g))
        v2024 = quantile_map(score, g["WGTP"].to_numpy(), tail["value_survey"].to_numpy())

        # Carry each value to 2026 market and just value with the household's own cell factors
        # (the same ones add_aged_values used), so all three stay consistent.
        out.loc[idx, "valp_2024"] = v2024
        out.loc[idx, "valp_market_aged"] = v2024 * g["value_growth"].to_numpy()
        out.loc[idx, "valp_jv_aged"] = v2024 * g["value_growth"].to_numpy() * g["jv_to_market"].to_numpy()
        out.loc[idx, "topcode_cutoff"] = tail["value_survey"].min()

        w = g["WGTP"].to_numpy()
        rows.append({"region": region, "records": len(g), "weighted": w.sum(), "tail_parcels": len(tail),
                     "statewide_cutoff_2024": cutoff,
                     "cutoff_2024": tail["value_survey"].min(), "tail_mean_2024": tail["value_survey"].mean(),
                     "tail_median_2024": tail["value_survey"].median(), "tail_max_2024": tail["value_survey"].max(),
                     "imputed_mean_2024": np.average(v2024, weights=w), "pums_topcode": g["VALP"].iloc[0],
                     # Spearman = Pearson on ranks (avoids a scipy dependency)
                     "tax_value_rank_corr": pd.Series(g["TAXAMT"].to_numpy()).rank().corr(pd.Series(v2024).rank())})
    return out, pd.DataFrame(rows)
