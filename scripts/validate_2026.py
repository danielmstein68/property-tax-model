"""Check the 2026 status quo against independent numbers -> data/processed/results/fl_2026_validation.json

Usage:
    python scripts/validate_2026.py

Two benchmarks:
  1. Property rolls (DOR NAL 2026): every residential homestead parcel's official school and
     non-school taxable value x its district's 2025 millage, compared with modelled homestead
     owners' tax at the same 2025 rates (tax_model_2026_2025rates). Same rates on both sides, so
     differences come from values, exemptions, who is homestead, and district assignment.
     Statewide, by county and by just-value band.
  2. Reported tax: households' own reported real estate tax (ACS TAXAMT, aged to 2026) vs the
     model, by income decile and years in home. Reported tax includes reporting error and, for
     some households, non-ad valorem fees; it is top-coded at $42,500.
"""

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ptm.millage import fl_dor_to_fips, load_rates  # noqa: E402
from ptm.results import add_income_deciles, owner_mask  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
YEAR = 2026
RES_UC = ["001", "002", "003", "004", "005", "008"]
BANDS = [0, 100e3, 200e3, 300e3, 400e3, 500e3, 750e3, 1e6, 2e6, np.inf]
BAND_LABELS = ["Under $100k", "$100–200k", "$200–300k", "$300–400k", "$400–500k", "$500–750k",
               "$750k–1M", "$1–2M", "$2M and over"]
MV_BANDS = {1: "Under 2 years", 2: "Under 2 years", 3: "2–4 years", 4: "5–9 years",
            5: "10–19 years", 6: "20 years or more", 7: "20 years or more"}


def roll_homesteads() -> pd.DataFrame:
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{YEAR}" / "co*.parquet"))
    cols = ["CO_NO", "DOR_UC", "JV", "TV_SD", "TV_NSD", "TAX_AUTH_CD", "homestead"]
    p = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    p = p[p["DOR_UC"].isin(RES_UC) & (p["JV"] > 0) & p["homestead"].fillna(False).astype(bool)]
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    rates = load_rates(2025).set_index(["county_fips", "code"])[["school_millage", "nonschool_millage"]]
    p = p.join(rates, on=["county_fips", "code"])
    p["tax"] = (p["TV_SD"] * p["school_millage"] + p["TV_NSD"] * p["nonschool_millage"]) / 1000
    return p


def wsum(x, w):
    return float((x * w).sum())


def main() -> None:
    b = pd.read_parquet(ROOT / "data" / "processed" / f"baseline_fl_{YEAR}.parquet")
    b = add_income_deciles(b)
    o = b[owner_mask(b)].copy()
    o["hs"] = o["homestead"].fillna(False).astype(bool)
    w = o["WGTP"]
    m = o[o["hs"]]
    mw = m["WGTP"]
    m_tax = m[f"tax_model_{YEAR}_2025rates"]
    m_tv = 0.37 * m[f"taxable_sd_{YEAR}"] + 0.63 * m[f"taxable_nsd_{YEAR}"]

    r = roll_homesteads()
    rated = r["tax"].notna()
    out = {"year": YEAR, "rates": "2025 district rates on both sides"}

    # 1a. statewide
    out["statewide_homestead"] = {
        "parcels_roll": int(len(r)), "owners_model": float(mw.sum()),
        "roll_parcels_with_rate": float(rated.mean()),
        "just_value_roll": float(r["JV"].sum()), "just_value_model": wsum(m["valp_jv_cal"], mw),
        "school_taxable_roll": float(r["TV_SD"].sum()), "school_taxable_model": wsum(m[f"taxable_sd_{YEAR}"], mw),
        "nonschool_taxable_roll": float(r["TV_NSD"].sum()), "nonschool_taxable_model": wsum(m[f"taxable_nsd_{YEAR}"], mw),
        "tax_roll": float(r.loc[rated, "tax"].sum() / rated.mean()), "tax_model": wsum(m_tax, mw),
        "avg_tax_roll": float(r.loc[rated, "tax"].mean()), "avg_tax_model": wsum(m_tax, mw) / float(mw.sum()),
        "median_tax_roll": float(r.loc[rated, "tax"].median()),
        "median_tax_model": float(np.interp(0.5, np.cumsum(mw.to_numpy()[np.argsort(m_tax.to_numpy())]) / mw.sum(),
                                             np.sort(m_tax.to_numpy()))),
    }

    # 1b. by county (district county)
    rc = r[rated].groupby("county_fips").agg(parcels=("tax", "size"), tax_roll=("tax", "sum"), jv_roll=("JV", "sum"))
    mc = m.assign(t=m_tax * mw, j=m["valp_jv_cal"] * mw).groupby("county_fips_tax").agg(
        owners=("WGTP", "sum"), tax_model=("t", "sum"), jv_model=("j", "sum"), records=("WGTP", "size"))
    c = rc.join(mc, how="outer")
    c["avg_tax_roll"] = c["tax_roll"] / c["parcels"]
    c["avg_tax_model"] = c["tax_model"] / c["owners"]
    c["avg_tax_ratio"] = c["avg_tax_model"] / c["avg_tax_roll"]
    c["count_ratio"] = c["owners"] / c["parcels"]
    c["rate_roll"] = c["tax_roll"] / c["jv_roll"]
    c["rate_model"] = c["tax_model"] / c["jv_model"]
    out["by_county"] = c.reset_index(names="county_fips").round(4).to_dict("records")

    # 1c. by just-value band
    r["band"] = pd.cut(r["JV"], BANDS, labels=BAND_LABELS)
    m = m.assign(band=pd.cut(m["valp_jv_cal"], BANDS, labels=BAND_LABELS))
    rb = r[rated].groupby("band", observed=False).agg(parcels=("tax", "size"), avg_tax_roll=("tax", "mean"),
                                                     tax=("tax", "sum"), jv=("JV", "sum"))
    rb["share_roll"] = rb["parcels"] / rb["parcels"].sum()
    rb["rate_roll"] = rb["tax"] / rb["jv"]
    g = m.assign(t=m_tax * mw, j=m["valp_jv_cal"] * mw).groupby("band", observed=False)
    mb = pd.DataFrame({"owners": g["WGTP"].sum(), "avg_tax_model": g["t"].sum() / g["WGTP"].sum(),
                       "rate_model": g["t"].sum() / g["j"].sum()})
    mb["share_model"] = mb["owners"] / mb["owners"].sum()
    out["by_value_band"] = rb.drop(columns=["tax", "jv"]).join(mb).reset_index().round(5).to_dict("records")

    # 2. reported vs modelled, all owners
    rep_ok = o["TAXAMT"].notna()
    o["rep"] = o["taxamt_aged"]
    o["mod"] = o[f"tax_model_{YEAR}"]
    o["years_in_home"] = o["MV"].map(MV_BANDS)

    def compare(by):
        g = o[rep_ok].assign(rw=o["rep"] * w, mw_=o["mod"] * w).groupby(by)
        t = pd.DataFrame({"owners": g["WGTP"].sum(), "avg_reported": g["rw"].sum() / g["WGTP"].sum(),
                          "avg_model": g["mw_"].sum() / g["WGTP"].sum()})
        t["ratio"] = t["avg_model"] / t["avg_reported"]
        return t.reset_index().round(4).to_dict("records")

    out["reported_statewide"] = {
        "total_reported": wsum(o["rep"].fillna(0), w), "total_model": wsum(o["mod"], w),
        "share_reporting_zero": float(w[o["TAXAMT"] == 0].sum() / w.sum()),
        "share_topcoded": float(w[o["flag_topcode_taxamt"].fillna(False).astype(bool)].sum() / w.sum()),
        "median_ratio_model_to_reported": float((o["mod"] / o["rep"])[o["rep"] > 0].median()),
        "share_within_25pct": float(w[(o["rep"] > 0) & ((o["mod"] / o["rep"] - 1).abs() <= 0.25)].sum() / w[o["rep"] > 0].sum()),
    }
    out["reported_by_decile"] = compare("income_decile")
    out["reported_by_years_in_home"] = compare("years_in_home")
    out["reported_by_homestead"] = compare("hs")

    dest = ROOT / "data" / "processed" / "results" / f"fl_{YEAR}_validation.json"
    dest.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
