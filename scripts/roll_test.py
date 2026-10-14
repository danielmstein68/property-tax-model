"""Roll test: does the rules engine reproduce the parcel roll's taxable values?

Usage:
    python scripts/roll_test.py            # 2026 Florida roll, residential parcels

For each residential parcel (DOR use 000-009) the engine gets the parcel's own assessed values
(AV_SD for school, AV_NSD for county/city/special) and its exemptions as recorded in the roll,
then its taxable values are compared with the roll's TV_SD (school) and TV_NSD (county).

Mapping roll exemption fields -> engine inputs:
  homestead                         EXMPT_01 > 0 (exemption granted on this parcel)
  av_homestead_portion              AV_HMSTD (homestead part of the parcel)
  homestead_share                   EXMPT_01 / min(25,000, homestead part) (co-owner proration)
  ex_vet_total                      EXMPT_05 or EXMPT_06 > 0
  ex_disabled_total                 EXMPT_08 > 0
  ex_first_responder                EXMPT_41 > 0
  ex_senior_longterm / _city        EXMPT_39 / EXMPT_40 > 0
  ex_senior_lowinc (+ amount)       EXMPT_03 (county amount); _city: EXMPT_04 (city amount)
  ex_widow_blind_disabled (count)   (EXMPT_31 + 32 + 33 + 34) / 5,000
  ex_disabled_exservice (count)     EXMPT_35 / 5,000
  ex_granny_flat (+ amount)         EXMPT_81
  ex_deployed_military (+ share)    EXMPT_38 / county value remaining before it
  ex_vet_discount (+ share)         EXMPT_80 / county value remaining before it (the roll records
                                    the county dollar amount; the engine applies the share per levy)
City-only exemptions (04, 40) don't affect TV_NSD, which is the county taxable value.
Exemption codes outside the spec (e.g. charitable, affordable housing) are flagged, not modelled.

Writes data/processed/roll_test/summary.csv (by county) and mismatches.parquet (sample + reasons).
"""

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.engine import apply_exemptions  # noqa: E402
from ptm.law import load_law  # noqa: E402

SPEC_CODES = {"01", "02", "03", "04", "05", "06", "08", "31", "32", "33", "34", "35", "38", "39", "40", "41", "80", "81"}
TOL = 1.0


def ex(d: pd.DataFrame, code: str) -> pd.Series:
    c = f"EXMPT_{code}"
    return d[c].fillna(0).astype(float) if c in d else pd.Series(0.0, index=d.index)


def to_units(d: pd.DataFrame) -> pd.DataFrame:
    u = pd.DataFrame(index=d.index)
    u["av_school"] = d["AV_SD"].fillna(0)
    for c in ["county", "municipal", "special"]:
        u[f"av_{c}"] = d["AV_NSD"].fillna(0)
    # Homestead exemption granted on this parcel (not just Save Our Homes status: contiguous
    # land can be assessed as homestead while the exemption sits on the house's parcel)
    e01 = ex(d, "01")
    u["homestead"] = e01 > 0
    # Homestead part of the property, and the share granted (co-owners who don't live there)
    portion = d["AV_HMSTD"].where(d["AV_HMSTD"].fillna(0) > 0, d["AV_SD"]).fillna(0)
    u["av_homestead_portion"] = portion
    full = np.minimum(portion, 25_000)
    u["homestead_share"] = np.where((e01 > 0) & (full > 0), np.minimum(e01 / full.where(full > 0, 1), 1), 1.0)
    u["ex_vet_total"] = (ex(d, "05") > 0) | (ex(d, "06") > 0)
    # Code 08 is the total disability exemption statewide, but Brevard records the $5,000
    # disability exemption there. Treat 08 as total only when it covers (nearly) the whole value.
    e08 = ex(d, "08")
    after_hs = (d["AV_SD"].fillna(0) - e01).clip(lower=0)
    total08 = (e08 > 0) & (e08 >= 0.95 * after_hs)
    u["ex_disabled_total"] = total08
    five08 = ((e08 > 0) & ~total08) * (e08 / 5000).round()
    u["ex_first_responder"] = ex(d, "41") > 0
    u["ex_senior_longterm"] = ex(d, "39") > 0
    u["ex_senior_longterm_city"] = ex(d, "40") > 0
    u["ex_senior_lowinc"], u["ex_senior_amount"] = ex(d, "03") > 0, ex(d, "03")
    u["ex_senior_lowinc_city"], u["ex_senior_city_amount"] = ex(d, "04") > 0, ex(d, "04")
    u["ex_widow_blind_disabled"] = ((ex(d, "31") + ex(d, "32") + ex(d, "33") + ex(d, "34")) / 5000).round() + five08
    u["ex_disabled_exservice"] = (ex(d, "35") / 5000).round()
    u["ex_granny_flat"], u["ex_granny_amount"] = ex(d, "81") > 0, ex(d, "81")
    # Percentage exemptions: share of the county value remaining before them
    dollar = sum(ex(d, c) for c in ["01", "02", "03", "31", "32", "33", "34", "35", "81"])
    before_mil = (d["AV_NSD"].fillna(0) - dollar).clip(lower=0)
    u["ex_deployed_military"] = ex(d, "38") > 0
    u["ex_deployed_share"] = (ex(d, "38") / before_mil.where(before_mil > 0)).fillna(0).clip(0, 1)
    before_disc = (before_mil - ex(d, "38")).clip(lower=0)
    u["ex_vet_discount"] = ex(d, "80") > 0
    u["ex_vet_discount_share"] = (ex(d, "80") / before_disc.where(before_disc > 0)).fillna(0).clip(0, 1)
    return u


def reasons(d: pd.DataFrame) -> pd.Series:
    """Label why a parcel might not match: exemption codes the spec doesn't cover, etc."""
    other = [c for c in d if c.startswith("EXMPT_") and c[-2:] not in SPEC_CODES]
    has_other = (d[other].fillna(0) > 0).any(axis=1) if other else pd.Series(False, index=d.index)
    r = pd.Series("", index=d.index)
    r[has_other] = "exemption outside spec"
    for code, lab in [("80", "veterans' discount"), ("35", "$5,000 ex-service"), ("38", "deployed military"),
                      ("03", "senior county"), ("81", "granny flat")]:
        r[(r == "") & (ex(d, code) > 0)] = lab
    r[(r == "") & (d["JV"].fillna(0) <= 10)] = "nominal $10 common element (not a home)"
    r[(r == "") & (d["CO_NO"].astype(int) == 30) & ((d["TV_NSD"] - (d["AV_NSD"] - 25_000 - 25_722)).abs() <= 1)] = \
        "county used 2025 second-band amount (Gadsden preliminary roll)"
    r[(r == "") & ~d["homestead"].astype(bool)] = "non-homestead, no listed exemption"
    r[r == ""] = "homestead, standard exemptions"
    return r


def main() -> None:
    law = load_law("fl")
    out_dir = ROOT / "data" / "processed" / "roll_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, bad = [], []
    for f in sorted(glob.glob(str(ROOT / "data" / "processed" / "fl_nal_2026" / "co*.parquet"))):
        d = pd.read_parquet(f).reset_index(drop=True)
        d = d[d["AV_SD"].notna() & d["TV_SD"].notna()]
        t = apply_exemptions(to_units(d), law, 2026)
        ok_sd = (t["taxable_school"] - d["TV_SD"]).abs() <= TOL
        ok_ns = (t["taxable_county"] - d["TV_NSD"]).abs() <= TOL
        rows.append({"county": Path(f).stem, "parcels": len(d), "school_exact": ok_sd.mean(),
                     "county_exact": ok_ns.mean(), "both_exact": (ok_sd & ok_ns).mean()})
        miss = ~(ok_sd & ok_ns)
        if miss.any():
            m = d.loc[miss, ["CO_NO", "PARCEL_ID", "DOR_UC", "homestead", "AV_SD", "AV_NSD", "TV_SD", "TV_NSD"]].copy()
            m["model_school"], m["model_county"] = t.loc[miss, "taxable_school"], t.loc[miss, "taxable_county"]
            m["school_ok"], m["county_ok"] = ok_sd[miss], ok_ns[miss]
            m["reason"] = reasons(d.loc[miss])
            bad.append(m)
    s = pd.DataFrame(rows)
    s.to_csv(out_dir / "summary.csv", index=False)
    b = pd.concat(bad) if bad else pd.DataFrame()
    b.to_parquet(out_dir / "mismatches.parquet", index=False)

    n = s["parcels"].sum()
    w = lambda col: (s[col] * s["parcels"]).sum() / n  # noqa: E731
    print(f"residential parcels: {n:,}")
    print(f"exact (within ${TOL:.0f}): school {w('school_exact'):.3%} | county {w('county_exact'):.3%} | both {w('both_exact'):.3%}")
    if len(b):
        print("\nmismatches by likely reason (parcels):")
        print(b.groupby("reason").agg(parcels=("reason", "size"), school_wrong=("school_ok", lambda x: (~x).sum()),
                                      county_wrong=("county_ok", lambda x: (~x).sum()))
              .sort_values("parcels", ascending=False).to_string())
        explained = {"exemption outside spec", "nominal $10 common element (not a home)",
                     "county used 2025 second-band amount (Gadsden preliminary roll)"}
        unexplained = (~b["reason"].isin(explained)).sum()
        print(f"\nexcluding explained out-of-scope / county-data cases: {1 - unexplained / n:.3%} exact "
              f"({unexplained:,} parcels left to explain)")
    print("\nlowest counties (both exact):")
    print(s.sort_values("both_exact").head(5)[["county", "parcels", "school_exact", "county_exact"]].to_string(index=False))


if __name__ == "__main__":
    main()
