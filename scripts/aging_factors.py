"""Compute income aging factors (survey year -> base year) and save them as a CSV.

Usage:
    python scripts/aging_factors.py --from-year 2024 --to-year 2026
    python scripts/aging_factors.py --state tx      # -> inputs/tx_aging_factors_2026.csv

Writes inputs/aging_factors_<to-year>.csv with one row per income type:
factor, measure, source.

Method: compare the same calendar months in both years (the months published
so far in the target year), which avoids seasonal bias and handles a target
year that isn't over yet. Months missing in either year are skipped
(e.g. October 2025 CPI was never published because of the government shutdown).

Measures:
  - wages, self-employment: Florida average weekly wage, private (BLS QCEW). QCEW counts every
    job covered by unemployment insurance, so it's more reliable for a state than the CES
    survey's average hourly earnings, which gave a higher +12.1% for 2024->2026 (sample noise
    and job-mix effects). Quarterly and ~6 months behind: compares the latest published
    quarter of the target year with the same quarter of the survey year.
  - Social Security, SSI: actual cost-of-living adjustments (SSA)
  - retirement, interest/dividends/rent, public assistance, other: CPI-U, US city average (BLS)
  - contract rent: CPI rent of primary residence by area (Miami and Tampa metro series; South
    region for the rest of Florida). CPI rent tracks what existing tenants pay, which suits PUMS
    renters (they're incumbents), not new-lease market rents.
  - utilities part of gross rent: CPI-U
"""

import argparse
import csv
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLS = "https://api.bls.gov/publicAPI/v1/timeseries/data/{sid}?startyear={a}&endyear={b}"
FL_QCEW_PRIVATE_WEEKLY_WAGE = "ENU1200040510"
CPI_U = "CUUR0000SA0"
CPI_RENT = {"miami": "CUURS35BSEHA", "tampa": "CUURS35DSEHA", "other_fl": "CUUR0300SEHA"}
# Texas: QCEW private average weekly wage, CPI rent for Dallas-Fort Worth and Houston, South region elsewhere
STATE = {"fl": {"name": "Florida", "qcew": FL_QCEW_PRIVATE_WEEKLY_WAGE, "rent": CPI_RENT, "out": "aging_factors_{y}.csv"},
         "tx": {"name": "Texas", "qcew": "ENU4800040510", "out": "tx_aging_factors_{y}.csv",
                "rent": {"dallas": "CUURS37ASEHA", "houston": "CUURS37BSEHA", "other_tx": "CUUR0300SEHA"}}}

# COLA paid in each year (announced the previous October). Source: SSA,
# https://www.ssa.gov/cola/ and https://blog.ssa.gov/social-security-announces-benefit-increase-for-2026
SS_COLA = {2025: 0.025, 2026: 0.028}

# Florida Save Our Homes cap: lesser of 3% or CPI change, by assessment year.
# Source: Florida DOR CPI table, https://www.floridarevenue.com/property/Documents/cpi_homestead_exemption.pdf
# (2026 CPI change 2.7%); county appraiser tables agree (2025: 2.9%, 2026: 2.7%).
FL_SOH_CAP = {2025: 0.029, 2026: 0.027}


def bls_monthly(series_id: str, a: int, b: int) -> dict[tuple[int, int], float]:
    with urllib.request.urlopen(BLS.format(sid=series_id, a=a, b=b)) as r:
        j = json.load(r)
    out = {}
    for x in j["Results"]["series"][0]["data"]:
        p = x["period"]
        if p[0] in "MQ" and p not in ("M13", "Q05") and x["value"] not in ("-", ""):
            out[(int(x["year"]), int(p[1:]))] = float(x["value"])  # month or quarter number
    return out


def same_period_ratio(series: dict, y0: int, y1: int, unit: str = "months") -> tuple[float, str]:
    periods = sorted(m for (y, m) in series if y == y1 and (y0, m) in series)
    v0 = sum(series[(y0, m)] for m in periods) / len(periods)
    v1 = sum(series[(y1, m)] for m in periods) / len(periods)
    return v1 / v0, f"{unit} {periods[0]}-{periods[-1]} of {y1} vs same {unit} of {y0}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from-year", type=int, default=2024)
    p.add_argument("--to-year", type=int, default=2026)
    p.add_argument("--state", default="fl", choices=sorted(STATE))
    args = p.parse_args()
    y0, y1 = args.from_year, args.to_year
    st = STATE[args.state]

    wage, wage_note = same_period_ratio(bls_monthly(st["qcew"], y0, y1), y0, y1, "quarters")
    cpi, cpi_note = same_period_ratio(bls_monthly(CPI_U, y0, y1), y0, y1)
    cola = 1.0
    for y in range(y0 + 1, y1 + 1):
        cola *= 1 + SS_COLA[y]

    wage_src = f"BLS QCEW {st['qcew']} {st['name']} avg weekly wage, private; {wage_note}"
    cpi_src = f"BLS {CPI_U} CPI-U US city avg; {cpi_note}"
    cola_src = "SSA COLAs " + ", ".join(f"{y}: {SS_COLA[y]:.1%}" for y in range(y0 + 1, y1 + 1))
    rows = [
        ("WAGP", "", "wages and salaries", wage, wage_src),
        ("SEMP", "", "self-employment income", wage, wage_src),
        ("SSP", "", "Social Security", cola, cola_src),
        ("SSIP", "", "Supplemental Security Income", cola, cola_src),
        ("RETP", "", "retirement and pension income", cpi, cpi_src),
        ("INTP", "", "interest, dividends, net rental income", cpi, cpi_src),
        ("PAP", "", "public assistance", cpi, cpi_src),
        ("OIP", "", "other income", cpi, cpi_src),
        ("UTIL", "", "utilities part of gross rent", cpi, cpi_src),
    ]
    if args.state == "fl":
        soh = 1.0
        for y in range(y0 + 1, y1 + 1):
            soh *= 1 + FL_SOH_CAP[y]
        rows.append(("TAXAMT", "", "property tax, PROVISIONAL (Save Our Homes caps, rates held fixed)", soh,
                     "FL Save Our Homes caps " + ", ".join(f"{y}: {FL_SOH_CAP[y]:.1%}" for y in range(y0 + 1, y1 + 1))
                     + "; FL DOR cpi_homestead_exemption.pdf"))
    for area, sid in st["rent"].items():
        f, note = same_period_ratio(bls_monthly(sid, y0, y1), y0, y1)
        rows.append(("RNTP", area, "contract rent", f, f"BLS {sid} CPI rent of primary residence; {note}"))

    out = ROOT / "inputs" / st["out"].format(y=y1)
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["variable", "area", "description", "from_year", "to_year", "factor", "source"])
        for var, area, desc, f, src in rows:
            w.writerow([var, area, desc, y0, y1, round(f, 5), src])
    for var, area, desc, f, _ in rows:
        print(f"{var:5s} {area:9s} {desc:40s} x{f:.4f}  ({f - 1:+.1%})")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
