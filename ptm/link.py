"""Link PUMS households to the parcel roll: tax-relevant facts PUMS doesn't have.

Each step answers one question needed to simulate a household's property tax, using the
base-year parcel roll for counts by PUMA and PUMS signals to pick which households.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.parcels import out_of_state
from ptm.geo import fl_parcel_counts_by_puma

ROOT = Path(__file__).resolve().parents[1]


def _roll(base_year: int, cols: list[str]) -> pd.DataFrame:
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    return pd.concat([pd.read_parquet(f, columns=cols) for f in files])


def _fill_by_priority(h: pd.DataFrame, eligible: pd.Series, target_by_puma: pd.Series,
                      priority: list[str], ascending: list[bool], group: str | list[str] = "PUMA") -> pd.Series:
    """Mark eligible households, highest priority first within each group (default PUMA), until
    their weights reach the group's target. A household is marked if that brings the total
    closer to the target."""
    marked = pd.Series(False, index=h.index)
    for puma, idx in h[eligible].groupby(group).groups.items():
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


# Roll use codes -> household home type, for homestead counts. Owners in duplexes and small
# buildings (PUMS BLD 4-9, our "condo") homestead on multi-family parcels (003, 008), and co-ops
# (005) are recorded separately, so all of these count as "condo".
ROLL_HOME_TYPE = {"001": "sfr", "004": "condo", "005": "condo", "008": "condo", "003": "condo", "002": "mobile"}


def householder_citizenship(persons_path) -> pd.DataFrame:
    """Householder's citizenship (CIT) per household, from the PUMS person file."""
    p = pd.read_csv(persons_path, usecols=["SERIALNO", "SPORDER", "CIT"], dtype={"SERIALNO": str})
    p = p[p["SPORDER"] == 1]
    return p[["SERIALNO", "CIT"]].rename(columns={"CIT": "hh_cit"})


def implied_rate_signal(h: pd.DataFrame, survey_year: int) -> pd.Series:
    """How far a household's reported tax is above what a homestead would pay.

    Implied rate if homestead = TAXAMT / homestead taxable value in the survey year (assessed
    value from add_aged_taxamt_rules, less the homestead exemption, school share as in
    ptm.aging.SCHOOL_SHARE). Compared with the weighted median implied rate among owners in the
    same PUMA with similar time in the home (MV bands 1-3, 4, 5-7): comparing with
    similar-tenure neighbours cancels systematic error in the estimated Save Our Homes gap,
    which otherwise made long-time owners look like non-claimers.
    signal = log2(implied / typical), clipped to [0, 3] — 1 means twice the typical rate, which
    is what a non-homestead (taxed on full just value, ~2x a homestead) looks like.
    0 for owners with $0 reported tax or top-coded value or tax (no usable evidence).
    """
    from ptm import florida
    from ptm.aging import SCHOOL_SHARE

    av = h[f"av_{survey_year}"].to_numpy(dtype=float)
    school, nonschool = florida.homestead_taxable(np.nan_to_num(av), survey_year)
    taxable = SCHOOL_SHARE * school + (1 - SCHOOL_SHARE) * nonschool
    usable = ((h["TAXAMT"] > 0) & ~h["flag_topcode_taxamt"] & ~h["flag_topcode_valp"]
              & h[f"av_{survey_year}"].notna()).to_numpy()
    rate = np.where(usable & (taxable > 0), h["TAXAMT"].to_numpy() / np.where(taxable > 0, taxable, 1), np.nan)
    rate = pd.Series(rate, index=h.index)

    def wmedian(g):
        g = g.dropna(subset=["rate"])
        if g.empty:
            return np.nan
        g = g.sort_values("rate")
        c = g["WGTP"].cumsum()
        return g["rate"].iloc[int(np.searchsorted(c, c.iloc[-1] / 2))]

    band = pd.cut(h["MV"], [0, 3, 4, 7], labels=["recent", "mid", "long"]).astype(str)
    cells = pd.DataFrame({"rate": rate, "WGTP": h["WGTP"], "PUMA": h["PUMA"], "band": band})
    typical = cells.groupby(["PUMA", "band"]).apply(wmedian)
    typical_hh = pd.Series(list(zip(h["PUMA"], band)), index=h.index).map(typical)
    sig = np.log2(rate / typical_hh)
    # Paying tax while the homestead rules say $0 taxable: strongest evidence
    sig[usable & (taxable <= 0)] = 3.0
    return sig.clip(lower=0, upper=3).fillna(0)


def assign_homestead(h: pd.DataFrame, base_year: int, persons_path, survey_year: int = 2024,
                     rate_weight: float = 1.0, tilt: float = 0.25,
                     seed: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Which owners claim the homestead exemption?

    Targets (roll): homestead parcels by PUMA x home type. Non-claimers in a cell = PUMS owners
    minus roll homesteads (clipped at 0), rescaled so each PUMA's total equals its PUMA-level gap
    (type labels don't line up perfectly between PUMS and the roll, so PUMA totals are what we
    trust). Mobile homes on rented lots are excluded (never homestead).

    Which households: score = random U(0,1) + rate_weight x implied-rate signal
    + tilt x (number of demographic signals); highest scores become non-claimers.
      - implied-rate signal (main): reported tax too high to be a homestead, given the
        household's estimated assessment gap and exemptions (implied_rate_signal). Requires
        add_aged_taxamt_rules first (av_<survey_year>).
      - demographic signals (smaller weight):
          non-citizen householder (CIT 5) — partial proxy for residency eligibility;
          snowbird profile: householder 65+ in a PUMA in the top third for out-of-state ownership
          of non-homestead homes (from the roll);
          very recent mover (MV 1) — may not own/live there on Jan 1 or may not have filed yet.
    rate_weight = tilt = 0 is purely random. Reasons PUMS can't see (LLC title, spouse
    elsewhere, never applied) are covered by the random part.

    Adds: homestead (bool, owners), non_claim_reason ('likely_ineligible' if non-citizen or
    snowbird profile; else 'possibly_eligible' — candidates for take-up if exemptions grow).
    Returns (households, report by PUMA).
    """
    out = h.copy()
    out["PUMA"] = out["PUMA"].astype(str).str.zfill(5)
    if "hh_cit" not in out:
        out = out.merge(householder_citizenship(persons_path), on="SERIALNO", how="left")
    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)

    roll = _roll(base_year, ["CO_NO", "CENSUS_BK", "DOR_UC", "homestead", "own_state"])
    roll["own_out_of_state"] = out_of_state(roll["own_state"])  # recomputed: stored flag wrong where state is spelled out
    roll["type"] = roll["DOR_UC"].map(ROLL_HOME_TYPE)
    roll = roll[roll["type"].notna()]
    for t in ["sfr", "condo", "mobile"]:
        roll[f"hs_{t}"] = ((roll["type"] == t) & roll["homestead"]).astype(float)
    homes = roll["DOR_UC"].isin(["001", "004", "005", "002"])
    roll["nh_home"] = (homes & ~roll["homestead"]).astype(float)
    roll["nh_home_out_of_state"] = (homes & ~roll["homestead"] & roll["own_out_of_state"]).astype(float)
    counts = fl_parcel_counts_by_puma(
        roll, ["hs_sfr", "hs_condo", "hs_mobile", "nh_home", "nh_home_out_of_state"]).set_index("PUMA")

    # Targets: cell gaps rescaled to the PUMA-level gap
    pums = out[owner].groupby(["PUMA", "home_type"])["WGTP"].sum().unstack(fill_value=0)
    hs = counts[["hs_sfr", "hs_condo", "hs_mobile"]].rename(columns=lambda c: c[3:]).reindex(pums.index).fillna(0)
    cell_gap = (pums - hs.reindex(columns=pums.columns, fill_value=0)).clip(lower=0)
    puma_gap = (pums.sum(axis=1) - hs.sum(axis=1)).clip(lower=0)
    scale = (puma_gap / cell_gap.sum(axis=1)).fillna(0)
    target = cell_gap.mul(scale, axis=0).stack()

    # Signals and score
    oos_share = counts["nh_home_out_of_state"] / counts["nh_home"]
    snowbird_area = out["PUMA"].map(oos_share >= oos_share.quantile(2 / 3)).fillna(False)
    out["_sig_noncitizen"] = out["hh_cit"] == 5
    out["_sig_snowbird"] = snowbird_area & (out["HHLDRAGEP"] >= 65)
    out["_sig_recent"] = out["MV"] == 1
    rng = np.random.default_rng(seed)
    signals = out[["_sig_noncitizen", "_sig_snowbird", "_sig_recent"]].sum(axis=1)
    out["implied_rate_signal"] = implied_rate_signal(out, survey_year)
    out["_score"] = rng.random(len(out)) + rate_weight * out["implied_rate_signal"] + tilt * signals

    non_claim = _fill_by_priority(out, owner, target, priority=["_score"], ascending=[False],
                                  group=["PUMA", "home_type"])
    out["homestead"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    out.loc[out["tenure"] == "owner", "homestead"] = owner & ~non_claim
    out["non_claim_reason"] = pd.NA
    likely_inel = out["_sig_noncitizen"] | out["_sig_snowbird"]
    out.loc[non_claim & likely_inel, "non_claim_reason"] = "likely_ineligible"
    out.loc[non_claim & ~likely_inel, "non_claim_reason"] = "possibly_eligible"

    report = pd.DataFrame({
        "pums_owners": pums.sum(axis=1),
        "roll_homesteads": hs.sum(axis=1),
        "target_non_claimers": puma_gap,
        "assigned_non_claimers": out[non_claim].groupby("PUMA")["WGTP"].sum(),
        "out_of_state_share": oos_share.reindex(pums.index),
    }).fillna(0)
    out = out.drop(columns=["_sig_noncitizen", "_sig_snowbird", "_sig_recent", "_score"])
    return out, report.reset_index()


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
