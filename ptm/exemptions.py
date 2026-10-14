"""Special homestead exemptions and the $0-tax owners.

The roll shows 3.9% of Florida homesteads have $0 taxable value — 77% because of the disabled
veterans' total exemption — and PUMS homesteads report $0 tax at almost the same rate (4.3%).
So most PUMS zeros are real. Here we give PUMS homesteads the exemptions that matter for tax,
matching roll counts by area, and classify the remaining $0 reports.

Exemption groups (codes in inputs/fl_exemption_codes.csv; rules in inputs/fl_law.yaml), in
assignment order, each matched to the roll's count of homesteads by county group:
  vet_total        05, 06  total; chosen mainly by reported $0 tax (+ veteran or widowed-65+
                           signal); PUMS's 70-100% rating band alone is too broad
  disabled_total   08      total; a member with ambulatory and self-care difficulty; $0 reporters
                           first, then gross household income under the s. 196.101 limit.
                           Brevard's $5,000 entries under code 08 are not counted here.
  senior_longterm  39      county levies, total; 65+, income under the limit, 25+ years in the home,
                           just value under $250,000 in the first qualifying year (deflated)
  senior_lowinc    03      county levies, the county group's own amount (roll median); 65+, income
                           under the limit
  vet_discount     80      % discount; veteran 65+ with a service-connected rating (DRAT 2-5)
  widow_blind_disabled 31-34 (+ Brevard 08)  $5,000; widowed householder, a blind member, or a
                           disabled adult
  disabled_exservice 35    $5,000; a veteran with a service-connected rating of 10%+
City versions (04, 40) are assigned in ptm.millage once tax districts are known.
Senior income test: household income minus Social Security and SSI, approximating adjusted gross
income (most Social Security of low-income seniors isn't taxable).
Within an area, candidates who report $0 tax (for total exemptions), or low tax relative to their
modelled pre-exemption taxable value (for the others), are chosen first.
Taxable value (school, county) and the $0-tax classification come from the rules engine.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import county_groups, fl_dor_to_fips, parcel_area
from ptm.link import _fill_by_priority

ROOT = Path(__file__).resolve().parents[1]
SENIOR_INCOME_LIMIT = {2026: 38_686}  # s. 196.075; county appraisers (Pasco, Nassau) for 2026
SENIOR_LONGTERM_JV_LIMIT = 250_000    # s. 196.075(2)(b): just value in the first year the owner qualifies
SENIOR_LONGTERM_FIRST_YEAR = 2013     # the long-term senior exemption began with the 2013 tax year
DISABLED_INCOME_LIMIT = {2026: 37_712}  # s. 196.101(4); gross household income incl. SS and VA (Daniel)
# County codes only: the city versions (04, 40) are assigned separately (ptm.millage).
GROUPS = {
    "vet_total": ["EXMPT_05", "EXMPT_06"],
    "disabled_total": ["EXMPT_08"],          # total only; Brevard's $5,000 code-08 entries excluded
    "senior_longterm": ["EXMPT_39"],
    "senior_lowinc": ["EXMPT_03"],
    "vet_discount": ["EXMPT_80"],
    "widow_blind_disabled": ["EXMPT_31", "EXMPT_32", "EXMPT_33", "EXMPT_34"],  # + Brevard's $5,000 code 08
    "disabled_exservice": ["EXMPT_35"],
}
TOTAL = ["vet_total", "disabled_total"]


def _code08_split(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Code 08 is the total disability exemption, except Brevard records the $5,000 disability
    exemption there. Total = covers (nearly) all value left after the $25k homestead exemption."""
    e08 = d["EXMPT_08"].fillna(0).to_numpy() if "EXMPT_08" in d else np.zeros(len(d))
    e01 = d["EXMPT_01"].fillna(0).to_numpy() if "EXMPT_01" in d else np.zeros(len(d))
    after = np.maximum(d["AV_SD"].fillna(0).to_numpy() - e01, 0)
    total = (e08 > 0) & (e08 >= 0.95 * after)
    return total, (e08 > 0) & ~total


def roll_exemption_counts(base_year: int) -> tuple[pd.DataFrame, dict]:
    """Homesteads with each exemption group, by county group (area); plus amounts.

    Returns (counts by area, amounts) where amounts has 'senior_lowinc_by_area' (median county
    low-income senior exemption per area) and 'vet_discount_share' (statewide median)."""
    rows, senior, disc = [], [], []
    for f in glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet")):
        d0 = pd.read_parquet(f)
        d0 = d0[d0["homestead"] & d0["DOR_UC"].isin(["001", "002", "004", "005"])]
        if d0.empty:
            continue
        for a, d in d0.groupby(parcel_area(d0)):  # one area per county, except split counties
            total08, five08 = _code08_split(d)
            row = {"area": a}
            for g, cols in GROUPS.items():
                has = np.zeros(len(d), bool)
                for c in cols:
                    if c in d:
                        has |= d[c].fillna(0).to_numpy() > 0
                if g == "disabled_total":
                    has = total08
                if g == "widow_blind_disabled":
                    has = has | five08
                row[g] = int(has.sum())
            rows.append(row)
            if "EXMPT_03" in d:
                senior.append(pd.DataFrame({"area": a, "amount": d.loc[d["EXMPT_03"] > 0, "EXMPT_03"]}))
            if "EXMPT_80" in d:
                x = d[d["EXMPT_80"] > 0]
                disc.append(x["EXMPT_80"] / x["AV_SD"].where(x["AV_SD"] > 0))
    counts = pd.DataFrame(rows).groupby("area").sum()
    s = pd.concat(senior) if senior else pd.DataFrame(columns=["area", "amount"])
    amounts = {"senior_lowinc_by_area": s.groupby("area")["amount"].median(),
               "senior_lowinc_state": float(s["amount"].median()) if len(s) else 50_000.0,
               "vet_discount_share": float(pd.concat(disc).median()) if disc else 0.0}
    return counts, amounts


def first_qualifying_jv(h: pd.DataFrame, survey_year: int, base_year: int) -> pd.Series:
    """Estimated just value in the first year the owner qualified for the long-term senior
    exemption: the later of (year turned 65) and (move-in year + 25), not before 2013; today's
    calibrated just value deflated by Florida's price index (inputs/fl_soh_history.csv)."""
    hist = pd.read_csv(ROOT / "inputs" / "fl_soh_history.csv").set_index("year")["hpi"]
    turned65 = survey_year - (h["HHLDRAGEP"] - 65)
    resident25 = h["purchase_year"] + 25
    q = np.maximum(np.maximum(turned65, resident25), SENIOR_LONGTERM_FIRST_YEAR).clip(upper=base_year)
    q = q.fillna(base_year).astype(int)
    return h["valp_jv_cal"] * q.map(hist).to_numpy() / hist.loc[base_year]


FLAG_COLS = ["vet_70plus", "vet_rated", "veteran", "severe_disability", "widowed_65", "widowed", "blind", "disabled_adult"]


def household_flags(persons_path) -> pd.DataFrame:
    p = pd.read_csv(persons_path, usecols=["SERIALNO", "SPORDER", "AGEP", "DRAT", "DIS", "DPHY", "DDRS", "DEYE",
                                           "MIL", "MAR"], dtype={"SERIALNO": str})
    p["vet_70plus"] = p["DRAT"] == 5
    p["vet_rated"] = p["DRAT"].isin([2, 3, 4, 5])           # service-connected rating 10%+
    p["veteran"] = p["MIL"] == 2  # served on active duty in the past
    p["severe_disability"] = (p["AGEP"] >= 18) & (p["DPHY"] == 1) & (p["DDRS"] == 1)
    p["widowed_65"] = (p["SPORDER"] == 1) & (p["MAR"] == 2) & (p["AGEP"] >= 65)
    p["widowed"] = (p["SPORDER"] == 1) & (p["MAR"] == 2)
    p["blind"] = p["DEYE"] == 1                             # vision difficulty (proxy for legally blind)
    p["disabled_adult"] = (p["AGEP"] >= 18) & (p["DIS"] == 1)
    return p.groupby("SERIALNO")[FLAG_COLS].any().reset_index()


def assign_exemptions(h: pd.DataFrame, base_year: int, persons_path, seed: int = 2026,
                      survey_year: int = 2024) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add ex_<group> flags to homesteads (matching roll counts by area), amounts, modelled
    taxable value (school, county) from the rules engine, and zero_tax_class for owners reporting
    $0: 'total_exemption', 'cheap_home' (modelled taxable under $5,000 — a tiny bill may be
    reported as $0), or 'misreported' (given a modelled tax from rates). Requires
    assign_assessment_gaps and add_aged_taxamt_rules (purchase_year).
    """
    from ptm import florida
    from ptm.engine import apply_exemptions
    from ptm.law import load_law

    out = h.copy()
    if "vet_70plus" not in out or "widowed" not in out:
        out = out.drop(columns=[c for c in FLAG_COLS if c in out]).merge(
            household_flags(persons_path), on="SERIALNO", how="left")
    for c in FLAG_COLS:
        out[c] = out[c].fillna(False).astype(bool)
    counts, amounts = roll_exemption_counts(base_year)
    rng = np.random.default_rng(seed)

    hs = (out["tenure"] == "owner") & (out["homestead"] == True)  # noqa: E712
    av_sd, av_nsd = out[f"av_sd_{base_year}"].fillna(0), out[f"av_nsd_{base_year}"].fillna(0)
    s, _ = florida.homestead_taxable(av_sd.to_numpy(), base_year)
    _, n = florida.homestead_taxable(av_nsd.to_numpy(), base_year)
    base_taxable = pd.Series(0.37 * s + 0.63 * n, index=out.index)
    # Low reported tax relative to modelled taxable -> more likely to have an extra exemption
    out["_low_tax"] = -(out["taxamt_aged"].fillna(0) / base_taxable.clip(lower=1)) + rng.random(len(out)) * 1e-6
    out["_zero_tax"] = out["TAXAMT"] == 0
    out["_rand"] = rng.random(len(out))

    age65 = out["HHLDRAGEP"] >= 65
    agi = out["hincp_aged"].fillna(0) - out.get("ssp_aged", 0) - out.get("ssip_aged", 0)
    low_inc = agi <= SENIOR_INCOME_LIMIT[base_year]
    # s. 196.101: gross income of everyone in the household, incl. Social Security and VA benefits
    disabled_low_gross = out["hincp_aged"].fillna(0) <= DISABLED_INCOME_LIMIT[base_year]
    zero = out["TAXAMT"] == 0
    # Veterans' total exemption: nearly every holder has $0 taxable (roll: 155,764 of 157,677), so
    # reported $0 is the main evidence. Tiers: $0 + veteran in household; $0 + widowed householder
    # 65+ (possible surviving spouse — PUMS can't flag them directly); $0 with no signal; then
    # rated 70-100% but paying tax (PUMS's 70-100% band is broader than the 100% P&T requirement).
    out["_vet_tier"] = np.select(
        [zero & (out["veteran"] | out["vet_rated"]), zero & out["widowed_65"], zero, out["vet_70plus"]],
        [3, 2, 1, 0], default=-1)
    # Total disability: $0 reporters first, then those under the gross-income limit (quadriplegics
    # have no income test, so higher-income households stay eligible, last).
    out["_dis_tier"] = np.select([zero & disabled_low_gross, zero, disabled_low_gross], [3, 2, 1], default=0)
    jv_first = first_qualifying_jv(out, survey_year, base_year)
    eligible = {
        "vet_total": hs & (out["_vet_tier"] >= 0),
        "disabled_total": hs & out["severe_disability"],
        "senior_longterm": hs & age65 & low_inc & ((survey_year - out["purchase_year"]) >= 25)
                           & (jv_first < SENIOR_LONGTERM_JV_LIMIT),
        "senior_lowinc": hs & age65 & low_inc,
        "vet_discount": hs & age65 & out["vet_rated"],
        "widow_blind_disabled": hs & (out["widowed"] | out["blind"] | out["disabled_adult"]),
        "disabled_exservice": hs & out["vet_rated"],
    }
    taken_total = pd.Series(False, index=out.index)
    report = []
    for g in GROUPS:
        elig = eligible[g] & ~taken_total
        if g == "vet_total":
            prio, asc = ["_vet_tier", "_rand"], [False, True]
        elif g == "disabled_total":
            prio, asc = ["_dis_tier", "_rand"], [False, True]
        elif g == "senior_longterm":
            prio, asc = ["_zero_tax", "_rand"], [False, True]
        else:
            prio, asc = ["_low_tax"], [False]
        got = _fill_by_priority(out, elig, counts[g], priority=prio, ascending=asc, group="value_area")
        out[f"ex_{g}"] = got
        if g in TOTAL:
            taken_total |= got
        report.append({"exemption": g, "roll_homesteads": int(counts[g].sum()),
                       "pums_eligible": out.loc[eligible[g], "WGTP"].sum(),
                       "assigned": out.loc[got, "WGTP"].sum()})
    # Eligibility kept for the city versions (ptm.millage assigns them once districts are known)
    out["elig_senior_lowinc"] = eligible["senior_lowinc"]
    out["elig_senior_longterm"] = eligible["senior_longterm"]
    by_area = amounts["senior_lowinc_by_area"]
    area_amount = out["value_area"].map(by_area).fillna(amounts["senior_lowinc_state"])
    out["ex_senior_amount"] = np.where(out["ex_senior_lowinc"], area_amount, 0.0)
    out["ex_vet_discount_share"] = np.where(out["ex_vet_discount"], amounts["vet_discount_share"], 0.0)
    for g in ["widow_blind_disabled", "disabled_exservice"]:
        out[f"ex_{g}"] = out[f"ex_{g}"].astype(int)          # count of $5,000 exemptions (1)

    # Modelled taxable value from the rules engine (school and county; city versions come later)
    law = load_law()
    u = out.copy()
    u["homestead"] = hs
    u["av_school"] = av_sd
    for c in ["county", "municipal", "special"]:
        u[f"av_{c}"] = av_nsd
    t = apply_exemptions(u, law, base_year)
    out[f"taxable_sd_{base_year}"] = t["taxable_school"]
    out[f"taxable_nsd_{base_year}"] = t["taxable_county"]

    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)
    zero = owner & (out["TAXAMT"] == 0)
    total = out["ex_vet_total"] | out["ex_disabled_total"]
    taxable = 0.37 * out[f"taxable_sd_{base_year}"] + 0.63 * out[f"taxable_nsd_{base_year}"]
    out["zero_tax_class"] = pd.NA
    out.loc[zero & (total | out["ex_senior_longterm"]), "zero_tax_class"] = "total_exemption"
    out.loc[zero & out["zero_tax_class"].isna() & (taxable < 5_000), "zero_tax_class"] = "cheap_home"
    out.loc[zero & out["zero_tax_class"].isna(), "zero_tax_class"] = "misreported"
    out = out.drop(columns=["_low_tax", "_zero_tax", "_rand", "_vet_tier", "_dis_tier"])
    return out, pd.DataFrame(report)
