"""Tax districts and rates for households, and modelled tax.

Rates (2025 final, the latest published; swap in 2026 when DOR posts it):
  inputs/fl_district_rates_<year>/<County>.csv  code -> total millage (and school, where shown)
  inputs/fl_school_millage_<year>.csv           countywide school millage (FLDOE)
Non-school millage = district total - countywide school millage.

PUMS households don't know their tax district, only their PUMA. Each owner gets the district of
a real roll parcel in the same PUMA x homestead status x value third. Within that cell, donors
are handed out in order of millage and households in order of the rate implied by their
reported tax (households paying more per dollar of taxable value are likely in higher-rate
districts, e.g. cities with their own levy); where reported tax isn't usable, order is random.
"""

import csv
import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ptm.geo import fl_dor_to_fips, fl_parcel_puma
from ptm.gaps import quantile_pick

ROOT = Path(__file__).resolve().parents[1]


def county_fips_by_name() -> dict[str, str]:
    """County name (as used in rate files) -> 3-digit FIPS, via the parcel manifest's DOR numbers."""
    out = {}
    with open(ROOT / "manifests" / "fl_nal_2026.csv") as fh:
        for r in csv.DictReader(fh):
            name = {"Dade": "Miami-Dade", "Saint Licie": "Saint Lucie"}.get(r["county"], r["county"])
            out[name] = fl_dor_to_fips(pd.Series([int(r["co_no"])])).iloc[0]
    return out


def load_rates(year: int = 2025) -> pd.DataFrame:
    """District rates for all counties with a rate file: county_fips, code, total, school, nonschool."""
    fips = county_fips_by_name()
    school = pd.read_csv(ROOT / "inputs" / f"fl_school_millage_{year}.csv")
    school = dict(zip(school["county"], school["total"]))
    frames = []
    for f in glob.glob(str(ROOT / "inputs" / f"fl_district_rates_{year}" / "*.csv")):
        county = Path(f).stem
        d = pd.read_csv(f, dtype={"code": str})
        d["county"], d["county_fips"] = county, fips.get(county)
        d["school_millage"] = school.get(county, np.nan)
        frames.append(d)
    r = pd.concat(frames, ignore_index=True)
    r["code"] = r["code"].str.strip()
    r = r.rename(columns={"total_millage_2025": "total_millage"})
    r["nonschool_millage"] = r["total_millage"] - r["school_millage"]
    return r[["county", "county_fips", "code", "total_millage", "school_millage", "nonschool_millage", "confidence"]]


def roll_districts(base_year: int) -> pd.DataFrame:
    """Residential roll parcels with PUMA (or county fallback), homestead, just value, district code."""
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    p = pd.concat([pd.read_parquet(f, columns=["CO_NO", "CENSUS_BK", "DOR_UC", "JV", "homestead", "TAX_AUTH_CD"])
                   for f in files], ignore_index=True)
    p = p[p["DOR_UC"].isin(["001", "002", "004", "005", "003", "008"]) & (p["JV"] > 0)]
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    p["PUMA"] = fl_parcel_puma(p)
    p["code"] = p["TAX_AUTH_CD"].astype(str).str.strip()
    return p[["county_fips", "PUMA", "homestead", "JV", "code"]]


def assign_districts(h: pd.DataFrame, base_year: int, rate_year: int = 2025, seed: int = 2026,
                     min_donors: int = 50) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Give each owner (not rented-lot mobile homes) a tax district and its millage; modelled tax.

    Requires assign_exemptions (taxable_sd_<base>, taxable_nsd_<base>).
    Cells: PUMA x homestead x value third (donors: roll parcels in the PUMA; parcels whose
    CENSUS_BK doesn't map to a PUMA are pooled by county and used for the county's PUMAs when the
    PUMA cell is thin). Adds county_fips_tax, tax_district, school_millage, nonschool_millage,
    tax_school_<base>, tax_nonschool_<base>, tax_model_<base> (2025 rates on 2026 taxable values).
    """
    from ptm.gaps import _bands

    rng = np.random.default_rng(seed)
    rates = load_rates(rate_year).set_index(["county_fips", "code"])
    roll = roll_districts(base_year)
    roll = roll.join(rates[["total_millage"]], on=["county_fips", "code"])
    roll = roll[roll["total_millage"].notna()]
    pct = roll.groupby(["PUMA", "homestead"])["JV"].rank(pct=True, method="first")
    roll["band"] = pd.cut(pct, [0, 1 / 3, 2 / 3, 1.0001], labels=["low", "mid", "high"]).astype(str)

    out = h.copy()
    owner = (out["tenure"] == "owner") & ~out["mh_rented_lot"].fillna(False).astype(bool)
    o = out[owner].copy()
    o["PUMA"] = o["PUMA"].astype(str).str.zfill(5)
    o["is_hs"] = (o["homestead"] == True).to_numpy()  # noqa: E712
    o["band"] = ""
    for _, idx in o.groupby(["PUMA", "is_hs"]).groups.items():
        o.loc[idx, "band"] = _bands(o.loc[idx, "valp_jv_cal"], o.loc[idx, "WGTP"])
    taxable = 0.37 * o[f"taxable_sd_{base_year}"] + 0.63 * o[f"taxable_nsd_{base_year}"]
    usable = (o["TAXAMT"] > 0) & ~o["flag_topcode_taxamt"] & (taxable > 1000)
    implied = (o["taxamt_aged"] / taxable).where(usable)
    o["_order"] = implied.groupby(o["PUMA"]).rank(pct=True).fillna(pd.Series(rng.random(len(o)), index=o.index))

    cells = {k: g for k, g in roll[roll["PUMA"].notna()].groupby(["PUMA", "homestead", "band"])}
    pumas = {k: g for k, g in roll[roll["PUMA"].notna()].groupby(["PUMA", "homestead"])}
    report = []
    for (puma, is_hs, band), idx in o.groupby(["PUMA", "is_hs", "band"]).groups.items():
        g = o.loc[idx]
        donors, level = cells.get((puma, is_hs, band)), "puma x homestead x band"
        if donors is None or len(donors) < min_donors:
            donors, level = pumas.get((puma, is_hs)), "puma x homestead"
        if donors is None or len(donors) < min_donors:
            report.append({"PUMA": puma, "homestead": is_hs, "band": band, "level": "no donors",
                           "records": len(g)})
            continue
        donors = donors.sort_values("total_millage", kind="stable")
        pos = quantile_pick(g["_order"].to_numpy(), g["WGTP"].to_numpy(), len(donors))
        pick = donors.iloc[pos]
        o.loc[idx, "county_fips_tax"] = pick["county_fips"].to_numpy()
        o.loc[idx, "tax_district"] = pick["code"].to_numpy()
        report.append({"PUMA": puma, "homestead": is_hs, "band": band, "level": level, "records": len(g),
                       "donors": len(donors)})

    o = o.join(rates[["school_millage", "nonschool_millage"]], on=["county_fips_tax", "tax_district"])
    for c in ["county_fips_tax", "tax_district", "school_millage", "nonschool_millage"]:
        out.loc[o.index, c] = o[c]
    out[f"tax_school_{base_year}"] = out[f"taxable_sd_{base_year}"] * out["school_millage"] / 1000
    out[f"tax_nonschool_{base_year}"] = out[f"taxable_nsd_{base_year}"] * out["nonschool_millage"] / 1000
    out[f"tax_model_{base_year}"] = out[f"tax_school_{base_year}"] + out[f"tax_nonschool_{base_year}"]
    return out, pd.DataFrame(report)
