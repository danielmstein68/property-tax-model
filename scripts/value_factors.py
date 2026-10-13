"""Build Florida home value aging inputs (survey year -> Jan 1 of the base year).

Usage:
    python scripts/value_factors.py

Step A: market value growth by county x type x tier, from Zillow's Home Value Index (ZHVI).
  Downloads the county ZHVI files to data/raw/zillow/ if missing. Growth runs from the
  survey-year average to the December before the base year (the ZHVI value closest to the
  Jan 1 assessment date). Zillow gives type (single-family, condo) and tier (bottom, middle,
  top third of values) as separate series, so:
      factor(county, type, tier) = type growth (middle tier) x tier growth / all-homes middle growth
  Mobile homes use the bottom-tier series. Counties without a condo series use single-family
  growth x the statewide median condo/single-family ratio.
  -> inputs/value_growth_fl_<base>.csv

Step B: just value / market value ratio by county x type x tier, from qualified (arm's-length,
  code 01) sales in the second half of the year before the base year, compared with the
  parcel's Jan 1 just value. Cells with fewer than MIN_SALES sales fall back to county x type,
  then to statewide type.
  -> inputs/just_value_ratio_fl_<base>.csv

ZHVI: Zillow Research, https://www.zillow.com/research/data/ (free with attribution).
"""

import argparse
import glob
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ZDIR = ROOT / "data" / "raw" / "zillow"
ZURL = "https://files.zillowstatic.com/research/public_csvs/zhvi/County_zhvi_uc_{}_sm_sa_month.csv"
SERIES = {
    "all_mid": "sfrcondo_tier_0.33_0.67",
    "sfr_mid": "sfr_tier_0.33_0.67",
    "condo_mid": "condo_tier_0.33_0.67",
    "bottom": "sfrcondo_tier_0.0_0.33",
    "top": "sfrcondo_tier_0.67_1.0",
}
MIN_SALES = 30
TYPE_FROM_DOR_UC = {"001": "sfr", "004": "condo", "005": "condo", "002": "mobile"}


def zhvi_growth(from_year: int, base_year: int) -> pd.DataFrame:
    """Growth from the from_year average to Dec of base_year - 1, per FL county and series."""
    ZDIR.mkdir(parents=True, exist_ok=True)
    end = f"{base_year - 1}-12-31"
    cols = {}
    for key, s in SERIES.items():
        path = ZDIR / f"County_zhvi_uc_{s}_sm_sa_month.csv"
        if not path.exists():
            urllib.request.urlretrieve(ZURL.format(s), path)
        z = pd.read_csv(path, dtype={"MunicipalCodeFIPS": str})
        z = z[z["State"] == "FL"]
        z = z.set_index(z["MunicipalCodeFIPS"].str.zfill(3))
        base = z[[c for c in z if c.startswith(f"{from_year}-")]].mean(axis=1)
        cols[key] = z[end] / base
        cols.setdefault("county", z["RegionName"].str.replace(" County", ""))
    return pd.DataFrame(cols)


def value_growth(from_year: int, base_year: int) -> pd.DataFrame:
    g = zhvi_growth(from_year, base_year)
    condo_ratio = (g["condo_mid"] / g["sfr_mid"]).median()
    condo = g["condo_mid"].fillna(g["sfr_mid"] * condo_ratio)
    rows = []
    for fips, r in g.iterrows():
        adj = {"bottom": r["bottom"] / r["all_mid"], "mid": 1.0, "top": r["top"] / r["all_mid"]}
        for tier, a in adj.items():
            rows.append((fips, r["county"], "sfr", tier, r["sfr_mid"] * a, "zhvi"))
            src = "zhvi" if pd.notna(r["condo_mid"]) else "sfr x statewide condo/sfr ratio"
            rows.append((fips, r["county"], "condo", tier, condo[fips] * a, src))
            rows.append((fips, r["county"], "mobile", tier, r["bottom"], "zhvi bottom tier (proxy)"))
    out = pd.DataFrame(rows, columns=["county_fips", "county", "type", "tier", "factor", "source"])
    out["from"] = f"{from_year} average"
    out["to"] = f"{base_year - 1}-12 (Jan 1 {base_year})"
    return out


def just_value_ratio(base_year: int) -> pd.DataFrame:
    cols = ["CO_NO", "CENSUS_BK", "DOR_UC", "JV", "SALE_PRC1", "SALE_YR1", "SALE_MO1", "QUAL_CD1"]
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    d = pd.concat([pd.read_parquet(f, columns=cols) for f in files])
    d = d[(d["SALE_YR1"] == base_year - 1) & (d["SALE_MO1"] >= 7) & (d["QUAL_CD1"] == "01")
          & (d["SALE_PRC1"] > 10_000) & d["DOR_UC"].isin(TYPE_FROM_DOR_UC)]
    d["type"] = d["DOR_UC"].map(TYPE_FROM_DOR_UC)
    d["county_fips"] = d["CENSUS_BK"].str[2:5]
    d = d[d["county_fips"].notna()]
    d["ratio"] = d["JV"] / d["SALE_PRC1"]
    d = d[d["ratio"].between(0.2, 3)]  # drop obvious mismatches (partial interests, data errors)
    # Tier: third of sale prices within the county (all types), like Zillow's tiers
    d["tier"] = d.groupby("county_fips")["SALE_PRC1"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["bottom", "mid", "top"]))

    cell = d.groupby(["county_fips", "type", "tier"], observed=True)["ratio"].agg(["median", "size"])
    ct = d.groupby(["county_fips", "type"])["ratio"].agg(["median", "size"])
    st = d.groupby("type")["ratio"].median()

    rows = []
    for fips in sorted(d["county_fips"].unique()):
        for typ in ["sfr", "condo", "mobile"]:
            for tier in ["bottom", "mid", "top"]:
                if (fips, typ, tier) in cell.index and cell.loc[(fips, typ, tier), "size"] >= MIN_SALES:
                    r, n, lvl = *cell.loc[(fips, typ, tier)], "county x type x tier"
                elif (fips, typ) in ct.index and ct.loc[(fips, typ), "size"] >= MIN_SALES:
                    r, n, lvl = *ct.loc[(fips, typ)], "county x type"
                else:
                    r, n, lvl = st[typ], (d["type"] == typ).sum(), "statewide type"
                rows.append((fips, typ, tier, round(float(r), 4), int(n), lvl))
    return pd.DataFrame(rows, columns=["county_fips", "type", "tier", "jv_to_market", "sales", "level"])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from-year", type=int, default=2024)
    p.add_argument("--base-year", type=int, default=2026)
    a = p.parse_args()
    (ROOT / "inputs").mkdir(exist_ok=True)

    g = value_growth(a.from_year, a.base_year)
    g.to_csv(ROOT / "inputs" / f"value_growth_fl_{a.base_year}.csv", index=False)
    print(f"value growth: {len(g)} rows; median factor by type:\n",
          g.groupby("type")["factor"].median().round(3).to_string())

    r = just_value_ratio(a.base_year)
    r.to_csv(ROOT / "inputs" / f"just_value_ratio_fl_{a.base_year}.csv", index=False)
    print(f"\njust value ratio: {len(r)} rows; levels used:\n", r["level"].value_counts().to_string())
    print("median ratio by type:\n", r.groupby("type")["jv_to_market"].median().round(3).to_string())


if __name__ == "__main__":
    main()
