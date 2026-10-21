"""Paying for a Texas property tax cut with the state sales tax -> data/processed/results/tx_offset_taxes.json

Usage:
    python scripts/tx_offset_taxes.py

As for Florida (scripts/offset_taxes.py): no new tax model. Each year's state cost is divided by what one
point of the state sales tax raises that year, and a point's cost to households comes from what they spend
on taxable items.

- What a point raises: state sales tax, all funds, from the Comptroller's Certification Revenue Estimate
  2026-27 (data/raw/tx_forecast/cre-2026-27-data.xlsx, Table A-16: FY 2026 $51.09B, FY 2027 $53.49B) over
  the 6.25% state rate. Property tax year y is paid in fiscal year y+1 (bills due Jan 31; the state fiscal
  year starts Sep 1). Past FY 2027 the base grows with Texas personal income: income per resident (wage
  path, inputs/tx_projection_assumptions.yaml) plus population (Texas Demographic Center).
- Who pays: Consumer Expenditure Survey 2024, Table 1110 (income tenths before taxes), spending on items in
  the sales tax base - Florida's item list (data/raw/fl_offset), which Texas's base resembles (groceries
  and medicine exempt in both); national spending patterns, grown with CPI. Part of the tax falls on
  businesses and visitors, so households' share is overstated.
For comparison: Lt. Gov. Patrick put replacing school property taxes at a sales tax of "14 or 15 cents"
(8.25 now) and all property taxes at "at least 25 cents" (docs/research/tx_policy_proposals.md).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ptm.economy import Economy  # noqa: E402
from ptm.tx.project import PATHS, SPEC, county_growth  # noqa: E402

CRE = ROOT / "data" / "raw" / "tx_forecast" / "cre-2026-27-data.xlsx"
STATE_RATE = 6.25
YEARS = range(2026, 2037)


def sales_tax_fy() -> dict[int, float]:
    d = pd.read_excel(CRE, sheet_name="Table A-16", header=None)
    yrs = [int(str(v).split()[0]) for v in d.iloc[1, 1:]]
    row = d[d[0].astype(str).str.strip() == "Sales Taxes"].iloc[0, 1:].astype(float).to_numpy() * 1000
    return dict(zip(yrs, row))


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from offset_taxes import taxable_spending   # Florida's CE item list
    e = Economy("central", assumptions_path=SPEC, paths_path=PATHS)
    fy = sales_tax_fy()
    pop = county_growth(range(2026, 2039)).sum(axis=0)
    v = dict(fy)
    for f in range(max(fy) + 1, 2038):
        g = (1 + e.rate("wage", min(f - 1, 2036))) * (pop[min(f - 1, 2038)] / pop[min(f - 2, 2038)]) - 1
        v[f] = v[f - 1] * (1 + g)
    point = {y: v[y + 1] / STATE_RATE for y in YEARS}
    ce = taxable_spending()
    cpi = {2024: 1.0}
    for y in range(2025, 2037):
        cpi[y] = cpi[y - 1] * (1 + e.rate("cpi", y)) if y >= 2026 else cpi[y - 1] * 1.027
    out = {"state_rate": STATE_RATE, "point_value": point, "sales_tax_fy": v,
           "taxable_spending_2024_by_decile": ce["taxable_spending_2024"], "ce_income_2024_by_decile": ce["ce_income_2024"],
           "cpi_index_from_2024": cpi, "items": ce["items"],
           "patrick": {"school_taxes_cents": "14 or 15 (from 8.25)", "all_property_taxes_cents": "at least 25"}}
    dest = ROOT / "data" / "processed" / "results" / "tx_offset_taxes.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print({y: round(point[y] / 1e9, 2) for y in YEARS})
    print("wrote", dest)


if __name__ == "__main__":
    main()
