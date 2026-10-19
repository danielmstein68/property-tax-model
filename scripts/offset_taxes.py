"""Paying for a property tax cut with other taxes -> data/processed/results/fl_offset_taxes.json

Usage:
    python scripts/offset_taxes.py

No new tax model: the pages divide each year's property tax revenue lost (rates unchanged) by what
one point of each tax raises that year. This script supplies those amounts and who pays a sales tax
increase. Sources (data/raw/fl_offset/, downloaded 2026-10-19):

- State sales tax and corporate income tax: General Revenue Estimating Conference, August 14, 2026
  (grchng.pdf p.1, $ millions, fiscal years). General Revenue gets 87.48% of the 6% sales tax after
  the statutory transfers to local governments (s. 212.20(6)(d): half-cent program 8.9744%, emergency
  0.0966%, county revenue sharing 2.0810%, municipal revenue sharing 1.3653%), so one point raises
  GR sales tax / 6 / 0.8748. All corporate income tax is General Revenue: one point = CIT / 5.5.
  Property tax roll year y is paid in fiscal year y-y+1; years past 2031-32 grow at the last year's rate.
- County sales surtaxes: Local Government Financial Information Handbook 2025 (lgfih25.pdf), DOR's
  estimate of a 1% levy by county for the local fiscal year ending September 30, 2026, and each
  county's unused room under the statutory caps (county government levies). The surtax applies to the
  first $5,000 of a single item, so a point raises less than a point of state tax. Grown with the
  state sales tax base.
- Who pays a sales tax increase: Consumer Expenditure Survey 2024, Table 1110 (deciles of income
  before taxes; cu-income-deciles-before-taxes-2024.xlsx), spending on items in Florida's sales tax
  base, per household by income tenth, grown with CPI. Applied to the model's Florida households by
  income tenth (national spending patterns; part of the tax falls on tourists and businesses).
- Amendment 3 only: the Revenue Estimating Conference's own loss by county (impact0710.pdf pp.6-9) for
  how many counties couldn't replace it within their unused surtax room.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RAW = ROOT / "data" / "raw" / "fl_offset"
OUT = ROOT / "data" / "processed" / "results" / "fl_offset_taxes.json"
YEARS = list(range(2027, 2037))
STATE_RATE, CIT_RATE = 6.0, 5.5
GR_SHARE = 1 - 0.089744 - 0.000966 - 0.020810 - 0.013653      # s. 212.20(6)(d)
# grchng.pdf p.1 (August 14, 2026), $ millions, FY 2025-26 actual then forecasts to FY 2031-32
GR = {"fy": [2025, 2026, 2027, 2028, 2029, 2030, 2031],
      "sales": [37437.3, 37942.5, 38799.9, 39917.0, 40973.3, 42146.8, 43352.6],
      "cit": [5919.1, 5888.7, 5877.8, 5958.4, 6016.0, 6092.5, 6172.2]}
# CE 2024 Table 1110 items in Florida's sales tax base (row of the item's name; its mean is the next row)
TAXABLE = ["Food away from home", "Alcoholic beverages", "Other lodging", "Other household expenses",
           "Housekeeping supplies", "Household furnishings and equipment", "Apparel and services",
           "Vehicle purchases (net outlay)", "Maintenance and repairs", "Vehicle rental, leases, licenses, and other charges",
           "Fees and admissions", "Audio and visual equipment and services", "Pets, toys, hobbies, and playground equipment",
           "Other entertainment supplies, equipment, and services", "Personal care products and services", "Reading",
           "Tobacco products and smoking supplies"]


def by_fiscal_year(series: list[float]) -> dict[int, float]:
    """Roll year y -> fiscal year y-(y+1) value ($), extended at the last growth rate."""
    v = dict(zip(GR["fy"], series))
    g = v[2031] / v[2030]
    out = {}
    for y in YEARS:
        out[y] = v[y] * 1e6 if y in v else v[2031] * g ** (y - 2031) * 1e6
    return out


def taxable_spending() -> dict:
    x = pd.read_excel(RAW / "cu-income-deciles-before-taxes-2024.xlsx", header=None)
    names = x[0].astype(str).str.strip()
    rows = []
    for item in TAXABLE:
        i = names[names == item].index
        assert len(i) == 1, item
        assert names[i[0] + 1] == "Mean", item
        rows.append(pd.to_numeric(x.iloc[i[0] + 1, 2:12], errors="coerce").fillna(0).to_numpy(float))
    total = np.sum(rows, axis=0)
    inc = pd.to_numeric(x.iloc[names[names == "Income before taxes"].index[0] + 1, 2:12]).to_numpy(float)
    return {"taxable_spending_2024": [round(v) for v in total], "ce_income_2024": [round(v) for v in inc],
            "items": TAXABLE}


def surtax() -> dict:
    import pypdf
    r = pypdf.PdfReader(RAW / "lgfih25.pdf")
    num = lambda s: int(s.replace(",", "").replace("$", "").replace("-", "0") or 0)
    counties, statewide = {}, None
    for pg in range(175, 184):
        for line in r.pages[pg - 1].extract_text().splitlines():
            line = line.strip()
            if line.startswith("Statewide"):
                v = re.findall(r"([\d,]+)\$", line)
                statewide = {"one_point": num(v[0]), "realized_county": num(v[1]), "unrealized_county": num(v[2]),
                             "realized_school": num(v[3]), "unrealized_school": num(v[4])}
                continue
            m = re.match(r"^([A-Z][A-Za-z .\-]+?)\s+([\d,]+)\$\s+([\d.]+)\s+([\d.]+)\s+(-|[\d,]+)\$\s+([\d.]+)\s+(-|[\d,]+)\$", line)
            if m:
                counties[m.group(1).strip()] = {"one_point": num(m.group(2)), "max_rate": float(m.group(3)), "rate": float(m.group(4)),
                                                "unused_rate": float(m.group(6)), "unused": num(m.group(7))}
    return {"statewide": statewide, "counties": counties}


def rec_county_losses() -> dict:
    """REC Amendment 3 loss by county and roll year (impact0710.pdf pp.6-9 cash: FY 27-28 = roll 2027)."""
    import pypdf
    r = pypdf.PdfReader(ROOT / "data" / "raw" / "fl_rec_amendment3" / "impact0710.pdf")
    out = {}
    for pg, y in zip(range(6, 10), range(2027, 2031)):
        for line in r.pages[pg - 1].extract_text().splitlines():
            m = re.match(r"^([A-Za-z_. \-]+?)\s+0\.0\s+0\.0\s+\(([\d,.]+)\)\s+\(", line.strip())
            if m and "Statewide" not in m.group(1):
                out.setdefault(m.group(1).replace("_", ". ").replace("St. ", "St. ").strip(), {})[y] = float(m.group(2).replace(",", "")) * 1e6
    return out


def main() -> None:
    from ptm.economy import Economy
    e = Economy("central")
    # 2024 -> 2025 CPI change: the Save Our Homes history's actual (its 2026 row holds 2025's change);
    # later years from the economy scenario
    hist = pd.read_csv(ROOT / "inputs" / "fl_soh_history.csv").set_index("year")
    cpi = {y: (1 + float(hist.loc[2026, "cpi_change"])) * e.index("cpi", 2025, y) for y in YEARS}
    sales = by_fiscal_year(GR["sales"])
    cit = by_fiscal_year(GR["cit"])
    sales_point = {y: sales[y] / STATE_RATE / GR_SHARE for y in YEARS}
    cit_point = {y: cit[y] / CIT_RATE for y in YEARS}
    st = surtax()
    growth = {y: sales[y] / (GR["sales"][0] * 1e6) for y in YEARS}       # surtax estimate is for FY 2025-26
    surtax_point = {y: st["statewide"]["one_point"] * growth[y] for y in YEARS}
    # Amendment 3: counties whose own loss (REC) is more than their unused county surtax room raises
    rec = rec_county_losses()
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower().replace("saint", "st"))
    cty = {norm(k): v for k, v in st["counties"].items()}
    short = {}
    for y in range(2027, 2031):
        n, have = 0, 0
        for name, losses in rec.items():
            c = cty.get(norm(name))
            if c is None or y not in losses:
                continue
            have += 1
            room = c["unused"] * growth[y]
            n += losses[y] > room
        short[str(y)] = {"counties_short": n, "counties": have}
    out = {"generated": pd.Timestamp.now().strftime("%Y-%m-%d"), "gr_share_of_sales_tax": round(GR_SHARE, 6),
           "state_rate": STATE_RATE, "cit_rate": CIT_RATE,
           "years": {str(y): {"sales_point": round(sales_point[y]), "cit_point": round(cit_point[y]),
                              "surtax_point": round(surtax_point[y]), "cpi_from_2024": round(cpi[y], 4)} for y in YEARS},
           "surtax_statewide": st["statewide"], "surtax_counties_parsed": len(st["counties"]),
           "a3_counties_short_of_surtax_room": short, **taxable_spending()}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for y in (2027, 2031, 2036):
        print(y, {k: f"${v/1e9:.2f}B" for k, v in (("sales point", sales_point[y]), ("CIT point", cit_point[y]), ("surtax point", surtax_point[y]))})
    print("surtax counties parsed:", len(st["counties"]), "| REC counties:", len(rec), "| short of room:", short)
    print("taxable spending by tenth (2024 $):", out["taxable_spending_2024"])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
