"""Panel of Florida millage and taxable value by government, 1995-2025 -> data/processed/millage_history.parquet

Usage:
    python scripts/fl_millage_history.py

Source: EDR Ad Valorem Tax Profiles (Office of Economic and Demographic Research, from BEBR and
DOR), one sheet per year, downloaded to data/raw/fl_edr_advalorem_profiles/:
  advaltxco.xlsx  counties (county-wide operating millage, county taxable value), 1996-2025
  advaltxmu.xlsx  municipalities (operating millage, taxable value), 1995-2025
  advaltxsd.xlsx  school districts (total operating millage, school taxable value), 1997-2025
Columns are found by their header text, since layouts change over the years.

Also writes data/processed/millage_changes.parquet: one row per government-year with
  x    log growth of the existing taxable base = log(TV[t] / TV[t-1]) + log(1 - new construction
       share), the share being the county's 2024-2026 average from the DOR Data Book
  dlm  log change in operating millage
(the rolled-back rate is last year's rate / exp(x), so dlm > -x means a rate above rolled-back).
Changes over 0.7 in absolute log terms are dropped (mergers, data errors).
"""

from pathlib import Path

import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RAW = ROOT / "data" / "raw" / "fl_edr_advalorem_profiles"
FILES = {"county": "advaltxco.xlsx", "municipal": "advaltxmu.xlsx", "school": "advaltxsd.xlsx"}


def _county_keys() -> set[str]:
    from ptm.millage import county_fips_by_name
    from ptm.ratemodel import norm
    keys = {norm(k) for k in county_fips_by_name()}
    return keys | {"dade", "miamidade", "desoto", "stjohns", "stlucie"}


def parse(kind: str) -> pd.DataFrame:
    from ptm.ratemodel import norm
    counties = _county_keys()
    sheets = pd.read_excel(RAW / FILES[kind], sheet_name=None, header=None)
    rows = []
    for name, d in sheets.items():
        if not str(name).strip().isdigit():
            continue
        year = int(str(name).strip())
        key_col = 1 if kind == "municipal" else 0
        is_row = d[key_col].map(lambda v: isinstance(v, str) and norm(v) in counties)
        first = int(is_row.idxmax())
        heads = [" ".join(str(v) for v in d.iloc[:first, j] if isinstance(v, str)).lower() for j in range(d.shape[1])]
        tv = next(j for j, h in enumerate(heads) if "taxable value" in h and "per capita" not in h)
        if kind == "school":
            mill = next(j for j, h in enumerate(heads) if "operating millage" in h)
        else:
            mill = next(j for j, h in enumerate(heads) if "millage" in h or j > tv + 1 and "operating" in h)
        for i in d.index[is_row]:
            tvv = pd.to_numeric(d.iat[i, tv], errors="coerce")
            mv = pd.to_numeric(d.iat[i, mill], errors="coerce")
            if pd.isna(tvv):
                continue
            rows.append({"kind": kind, "name": str(d.iat[i, 0]).strip(), "county": str(d.iat[i, key_col]).strip(),
                         "year": year, "taxable_value": float(tvv), "millage": float(mv) if not pd.isna(mv) else np.nan})
    return pd.DataFrame(rows)


def changes(d: pd.DataFrame) -> pd.DataFrame:
    from ptm.ratemodel import load_databook, norm
    db = load_databook()
    db["nc_share"] = db[["nc_2024", "nc_2025", "nc_2026"]].sum(axis=1) / db[["tv_2024", "tv_2025", "tv_2026"]].sum(axis=1)
    ncs = dict(zip(db["key"], db["nc_share"]))
    ncs["dade"] = ncs.get("miamidade")
    d = d.copy()
    d["nc"] = d["county"].map(norm).map(ncs).fillna(db["nc_share"].median())
    d = d.sort_values(["kind", "name", "county", "year"])
    g = d.groupby(["kind", "name", "county"])
    d["dlm"] = np.log(d["millage"] / g["millage"].shift())
    d["x"] = np.log(d["taxable_value"] / g["taxable_value"].shift()) + np.log(1 - d["nc"])
    ok = np.isfinite(d["dlm"]) & np.isfinite(d["x"]) & (d["millage"] > 0) & (d["dlm"].abs() < 0.7) & (d["x"].abs() < 0.7)
    return d.loc[ok, ["kind", "name", "county", "year", "x", "dlm"]].reset_index(drop=True)


def main() -> None:
    d = pd.concat([parse(k) for k in FILES], ignore_index=True)
    dest = ROOT / "data" / "processed" / "millage_history.parquet"
    d.to_parquet(dest, index=False)
    print(f"wrote {dest}: {len(d)} rows")
    ch = changes(d)
    ch.to_parquet(ROOT / "data" / "processed" / "millage_changes.parquet", index=False)
    print(f"wrote millage_changes.parquet: {len(ch)} government-years", ch.groupby("kind").size().to_dict())
    print(d.groupby("kind").agg(units=("name", "nunique"), years=("year", "nunique"), first=("year", "min"),
                                last=("year", "max"), millage_median=("millage", "median")))
    print(d[d.kind == "county"].groupby("year").apply(
        lambda g: pd.Series({"n": len(g), "median_mill": g.millage.median(), "tv_bn": g.taxable_value.sum() / 1e9})).round(3).to_string())


if __name__ == "__main__":
    main()
