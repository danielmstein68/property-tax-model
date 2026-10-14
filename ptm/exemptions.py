"""Special homestead exemptions and the $0-tax owners.

The roll shows 3.9% of Florida homesteads have $0 taxable value — 77% because of the disabled
veterans' total exemption — and PUMS homesteads report $0 tax at almost the same rate (4.3%).
So most PUMS zeros are real. Here we give PUMS homesteads the exemptions that matter for tax,
matching roll counts by area, and classify the remaining $0 reports.

Exemption groups (codes in inputs/fl_exemption_codes.csv), in assignment order:
  vet_total        05, 06  total; chosen mainly by reported $0 tax (+ veteran or widowed-65+
                           signal); PUMS's 70-100% rating band alone is too broad
  disabled_total   08      total; PUMS: an adult with ambulatory and self-care difficulty
  senior_longterm  39, 40  total on county/city levies; 65+, income under the limit, 20+ years in
                           the home (MV 6-7), just value under SENIOR_LONGTERM_JV_LIMIT
  senior_lowinc    03, 04  up to $50k off county/city levies; 65+, income under the limit
  vet_discount     80      % discount; veteran 65+ with a service-connected rating (DRAT 2-5)
Income test: household income minus Social Security and SSI, approximating adjusted gross income
(most Social Security of low-income seniors isn't taxable).
Within an area, candidates who report $0 tax (for total exemptions), or low tax relative to their
modelled pre-exemption taxable value (for the others), are chosen first.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import county_groups, fl_dor_to_fips
from ptm.link import _fill_by_priority

ROOT = Path(__file__).resolve().parents[1]
SENIOR_INCOME_LIMIT = {2026: 38_686}  # s. 196.075; county appraisers (Pasco, Nassau) for 2026
SENIOR_LONGTERM_JV_LIMIT = 350_000    # approximate; statute limit applies at first qualification
GROUPS = {
    "vet_total": ["EXMPT_05", "EXMPT_06"],
    "disabled_total": ["EXMPT_08"],
    "senior_longterm": ["EXMPT_39", "EXMPT_40"],
    "senior_lowinc": ["EXMPT_03", "EXMPT_04"],
    "vet_discount": ["EXMPT_80"],
}
TOTAL = ["vet_total", "disabled_total"]


def roll_exemption_counts(base_year: int) -> tuple[pd.DataFrame, dict]:
    """Homesteads with each exemption group, by county group (area); plus median amounts."""
    area = county_groups().drop_duplicates("county_fips").set_index("county_fips")["area"]
    rows, amounts = [], {"senior_lowinc": [], "vet_discount_share": []}
    for f in glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet")):
        d = pd.read_parquet(f)
        d = d[d["homestead"] & d["DOR_UC"].isin(["001", "002", "004", "005"])]
        a = area.get(fl_dor_to_fips(d["CO_NO"].iloc[:1]).iloc[0]) if len(d) else None
        row = {"area": a}
        for g, cols in GROUPS.items():
            has = np.zeros(len(d), bool)
            for c in cols:
                if c in d:
                    has |= d[c].fillna(0).to_numpy() > 0
            row[g] = int(has.sum())
        rows.append(row)
        if "EXMPT_03" in d:
            amounts["senior_lowinc"].append(d.loc[d["EXMPT_03"] > 0, "EXMPT_03"])
        if "EXMPT_80" in d:
            x = d[d["EXMPT_80"] > 0]
            amounts["vet_discount_share"].append(x["EXMPT_80"] / x["AV_SD"].where(x["AV_SD"] > 0))
    counts = pd.DataFrame(rows).groupby("area").sum()
    med = {k: float(pd.concat(v).median()) for k, v in amounts.items() if v}
    return counts, med


def household_flags(persons_path) -> pd.DataFrame:
    p = pd.read_csv(persons_path, usecols=["SERIALNO", "SPORDER", "AGEP", "DRAT", "DIS", "DPHY", "DDRS", "MIL", "MAR"],
                    dtype={"SERIALNO": str})
    p["vet_70plus"] = p["DRAT"] == 5
    p["vet_rated"] = p["DRAT"].isin([2, 3, 4, 5])
    p["veteran"] = p["MIL"] == 2  # served on active duty in the past
    p["severe_disability"] = (p["AGEP"] >= 18) & (p["DPHY"] == 1) & (p["DDRS"] == 1)
    p["widowed_65"] = (p["SPORDER"] == 1) & (p["MAR"] == 2) & (p["AGEP"] >= 65)
    cols = ["vet_70plus", "vet_rated", "veteran", "severe_disability", "widowed_65"]
    return p.groupby("SERIALNO")[cols].any().reset_index()


def assign_exemptions(h: pd.DataFrame, base_year: int, persons_path, seed: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add ex_<group> flags to homesteads (matching roll counts by area), ex_senior_amount, and
    zero_tax_class for owners reporting $0: 'total_exemption', 'cheap_home' (modelled taxable
    after exemptions under $5,000 — a tiny bill may be reported as $0), or 'misreported'
    (to be given a modelled tax at calibration). Requires assign_assessment_gaps.
    """
    from ptm import florida

    out = h.copy()
    if "vet_70plus" not in out:
        out = out.merge(household_flags(persons_path), on="SERIALNO", how="left")
    for c in ["vet_70plus", "vet_rated", "veteran", "severe_disability", "widowed_65"]:
        out[c] = out[c].fillna(False).astype(bool)
    counts, med = roll_exemption_counts(base_year)
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
    # Veterans' total exemption: nearly every holder has $0 taxable (roll: 155,764 of 157,677), so
    # reported $0 is the main evidence. Tiers: $0 + veteran in household; $0 + widowed householder
    # 65+ (possible surviving spouse — PUMS can't flag them directly); $0 with no signal; then
    # rated 70-100% but paying tax (PUMS's 70-100% band is broader than the 100% P&T requirement).
    zero = out["TAXAMT"] == 0
    out["_vet_tier"] = np.select(
        [zero & (out["veteran"] | out["vet_rated"]), zero & out["widowed_65"], zero, out["vet_70plus"]],
        [3, 2, 1, 0], default=-1)
    eligible = {
        "vet_total": hs & (out["_vet_tier"] >= 0),
        "disabled_total": hs & out["severe_disability"],
        "senior_longterm": hs & age65 & low_inc & (out["MV"] >= 6) & (out["valp_jv_cal"] < SENIOR_LONGTERM_JV_LIMIT),
        "senior_lowinc": hs & age65 & low_inc,
        "vet_discount": hs & age65 & out["vet_rated"],
    }
    taken_total = pd.Series(False, index=out.index)
    report = []
    for g in GROUPS:
        elig = eligible[g] & ~taken_total
        if g == "vet_total":
            prio, asc = ["_vet_tier", "_rand"], [False, True]
        elif g in TOTAL + ["senior_longterm"]:
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
    out["ex_senior_amount"] = np.where(out["ex_senior_lowinc"], med.get("senior_lowinc", 50_000), 0.0)
    out["ex_vet_discount_share"] = np.where(out["ex_vet_discount"], med.get("vet_discount_share", 0.0), 0.0)

    # Modelled taxable after special exemptions (rates come at calibration)
    total = out["ex_vet_total"] | out["ex_disabled_total"]
    school = np.where(total, 0, s)
    nonschool = np.where(total | out["ex_senior_longterm"], 0, np.maximum(n - out["ex_senior_amount"], 0))
    disc = 1 - out["ex_vet_discount_share"]
    out[f"taxable_sd_{base_year}"] = np.where(hs, school * disc, av_sd)
    out[f"taxable_nsd_{base_year}"] = np.where(hs, nonschool * disc, av_nsd)

    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)
    zero = owner & (out["TAXAMT"] == 0)
    taxable = 0.37 * out[f"taxable_sd_{base_year}"] + 0.63 * out[f"taxable_nsd_{base_year}"]
    out["zero_tax_class"] = pd.NA
    out.loc[zero & (total | out["ex_senior_longterm"]), "zero_tax_class"] = "total_exemption"
    out.loc[zero & out["zero_tax_class"].isna() & (taxable < 5_000), "zero_tax_class"] = "cheap_home"
    out.loc[zero & out["zero_tax_class"].isna(), "zero_tax_class"] = "misreported"
    out = out.drop(columns=["_low_tax", "_zero_tax", "_rand", "_vet_tier"])
    return out, pd.DataFrame(report)
