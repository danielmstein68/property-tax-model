"""Build Florida Save Our Homes history: annual cap and house price index.

Usage:
    python scripts/fl_soh_history.py

Writes inputs/fl_soh_history.csv with one row per year:
  cpi_change  CPI-U annual-average change for the *preceding* calendar year (CPIAUCNS via FRED)
  soh_cap     Save Our Homes cap for that assessment year = min(3%, cpi_change); official
              values where known (OFFICIAL_CAP)
  hpi         FHFA Florida purchase-only index, annual average of quarterly NSA values

The cap applies from 1995 (first year of Save Our Homes). Used to estimate each PUMS owner's
assessed/just value ratio from when they moved in.
"""


import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# CPI-U (BLS CUUR0000SA0) via FRED, which needs no key; the BLS API allows only 25 keyless
# requests a day.
FRED_CPI = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"

# Official caps override the computed ones where known (FL DOR / county appraiser tables).
# The computed 2026 cap (2.6%) differs from the official 2.7%, likely because October 2025
# CPI was never published.
OFFICIAL_CAP = {2024: 0.030, 2025: 0.029, 2026: 0.027}
FHFA_STATE = ROOT / "data" / "raw" / "fhfa" / "hpi_po_state.txt"
FHFA_STATE_URL = "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_po_state.txt"


def cpi_annual(first: int, last: int) -> pd.Series:
    """Annual-average CPI-U (complete years only)."""
    c = pd.read_csv(FRED_CPI)
    c.columns = ["date", "cpi"]
    c["year"] = c["date"].str[:4].astype(int)
    c["cpi"] = pd.to_numeric(c["cpi"], errors="coerce")
    g = c.dropna().groupby("year")["cpi"].agg(["mean", "size"])
    g = g[(g["size"] >= 11) & g.index.to_series().between(first, last)]  # Oct 2025 was never published
    return g["mean"]


def main() -> None:
    cpi = cpi_annual(1990, 2025)
    if not FHFA_STATE.exists():
        FHFA_STATE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(FHFA_STATE_URL, FHFA_STATE)
    f = pd.read_csv(FHFA_STATE, sep="\t")
    hpi = f[f["state"] == "FL"].groupby("yr")["indx_nsa"].mean()

    years = range(1991, 2027)
    rows = []
    for y in years:
        chg = cpi[y - 1] / cpi[y - 2] - 1 if (y - 2) in cpi and (y - 1) in cpi else None
        cap = min(0.03, max(chg, 0.0)) if (chg is not None and y >= 1995) else None
        cap = OFFICIAL_CAP.get(y, cap)
        rows.append((y, chg, cap, hpi.get(y)))
    out = pd.DataFrame(rows, columns=["year", "cpi_change", "soh_cap", "hpi"])
    dest = ROOT / "inputs" / "fl_soh_history.csv"
    out.round(5).to_csv(dest, index=False)
    print(out.tail(8).to_string(index=False))
    print(f"saved {dest}")


if __name__ == "__main__":
    main()
