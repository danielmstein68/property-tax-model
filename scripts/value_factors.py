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
  Level correction: Zillow overstates Florida's decline vs actual sales, so each county x type
  factor is multiplied by Zillow's annual bias (actual / Zillow, Jan-Jun year-on-year from the
  roll's qualified sales, shrunk toward the statewide bias for counties with few sales), raised
  to the length of the aging span. Zillow keeps the pattern; sales set the level. Assumes the
  bias measured for 2025->2026 also held in 2024->2025.
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


def load_sales(base_year: int) -> pd.DataFrame:
    """Qualified sales recorded in the base-year roll (both sale slots), one row per sale."""
    cols = ["CENSUS_BK", "DOR_UC", "JV", "TOT_LVG_AREA", "ACT_YR_BLT",
            "SALE_PRC1", "SALE_YR1", "SALE_MO1", "QUAL_CD1", "SALE_PRC2", "SALE_YR2", "SALE_MO2", "QUAL_CD2"]
    files = glob.glob(str(ROOT / "data" / "processed" / f"fl_nal_{base_year}" / "co*.parquet"))
    d = pd.concat([pd.read_parquet(f, columns=cols) for f in files])
    d = d[d["DOR_UC"].isin(TYPE_FROM_DOR_UC)]
    base = d[["CENSUS_BK", "DOR_UC", "JV", "TOT_LVG_AREA", "ACT_YR_BLT"]]
    s = pd.concat([base.assign(price=d[f"SALE_PRC{i}"], year=d[f"SALE_YR{i}"], month=d[f"SALE_MO{i}"],
                               qual=d[f"QUAL_CD{i}"]) for i in (1, 2)])
    s = s[(s["qual"] == "01") & (s["price"] > 10_000)]
    s["type"] = s["DOR_UC"].map(TYPE_FROM_DOR_UC)
    s["county_fips"] = s["CENSUS_BK"].str[2:5]
    return s[s["county_fips"].notna()]


SHRINK_N = 300  # sales at which a county's own correction gets half weight vs the statewide one


def zillow_bias(base_year: int, counties) -> pd.DataFrame:
    """Zillow's annual error vs actual sales, by county and type (sfr, condo).

    Compares Jan-Jun of base_year - 1 with Jan-Jun of base_year (the only full overlap the
    roll's sales allow). Actual change = change in the median ratio of sale price to the same
    parcel's Jan 1 base-year just value (a sale-price-to-appraisal ratio index): every parcel
    has an appraisal on the same date, so differences in which homes sold cancel out. (Median
    price per sq ft was tried first and was badly skewed by new-home sales and post-hurricane
    distressed sales.) Homes built in base_year - 1 or later are excluded.
    bias = actual / Zillow (middle tier for the type). County estimates are shrunk toward the
    statewide estimate: weight = n / (n + SHRINK_N), n = sales in the later period.
    """
    y0, y1 = base_year - 1, base_year
    s = load_sales(base_year)
    s = s[s["type"].isin(["sfr", "condo"]) & s["month"].between(1, 6) & s["year"].isin([y0, y1])
          & (s["ACT_YR_BLT"].fillna(0) < y0) & (s["JV"] > 0)]
    s["ppsf"] = s["price"] / s["JV"]  # sale price / appraisal ratio
    s = s[s["ppsf"].between(0.5, 3)]

    def zillow_h1(series_key: str) -> pd.Series:
        z = pd.read_csv(ZDIR / f"County_zhvi_uc_{SERIES[series_key]}_sm_sa_month.csv", dtype={"MunicipalCodeFIPS": str})
        z = z[z["State"] == "FL"]
        z = z.set_index(z["MunicipalCodeFIPS"].str.zfill(3))
        h1 = lambda y: z[[c for c in z if c[:7] in [f"{y}-0{m}" for m in range(1, 7)]]].mean(axis=1)
        return h1(y1) / h1(y0)

    rows = []
    for typ, key in [("sfr", "sfr_mid"), ("condo", "condo_mid")]:
        x = s[s["type"] == typ]
        med = x.groupby(["county_fips", "year"])["ppsf"].median().unstack()
        n = x[x["year"] == y1].groupby("county_fips").size()
        actual = (med[y1] / med[y0]).dropna()
        zr = zillow_h1(key)
        both = pd.concat([actual.rename("actual"), zr.rename("zillow"), n.rename("n")], axis=1).dropna()
        both["bias"] = both["actual"] / both["zillow"]
        state = np.average(both["bias"], weights=both["n"])
        for fips in counties:  # every FL county; no own estimate -> statewide
            if fips in both.index:
                nn = both.loc[fips, "n"]
                wgt = nn / (nn + SHRINK_N)
                b = wgt * both.loc[fips, "bias"] + (1 - wgt) * state
                rows.append((fips, typ, b, int(nn), round(wgt, 2)))
            else:
                rows.append((fips, typ, state, 0, 0.0))
    return pd.DataFrame(rows, columns=["county_fips", "type", "bias_annual", "sales", "county_weight"])


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
    out = pd.DataFrame(rows, columns=["county_fips", "county", "type", "tier", "zillow_factor", "source"])

    # Level correction from actual sales: Zillow's annual bias, applied over the aging span
    # (mid-from_year to Dec of base_year - 1). Mobile homes use the single-family correction.
    span_years = (base_year - 1 + 11.5 / 12) - (from_year + 0.5)
    bias = zillow_bias(base_year, sorted(g.index))
    bias_type = out["type"].replace({"mobile": "sfr"})
    key = pd.MultiIndex.from_arrays([out["county_fips"], bias_type])
    b = bias.set_index(["county_fips", "type"])["bias_annual"].reindex(key).to_numpy()
    out["bias_annual"] = b
    out["correction"] = b ** span_years
    out["factor"] = out["zillow_factor"] * out["correction"]
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
