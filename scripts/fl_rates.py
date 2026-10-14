"""Download Florida DOR tax rate files listed in manifests/fl_rates_<year>.csv.

Usage:
    python scripts/fl_rates.py              # 2025
    python scripts/fl_rates.py --year 2025

Two kinds of file (PDF, one per county):
  tacd    Taxing Authority Code Descriptions: each tax district code (TAX_AUTH_CD in the parcel
          roll) and its millage by component (school, county, city, special districts).
          2025: 58 counties; Baker, Brevard, Broward, Gadsden, Hernando, Lee, Liberty, Palm Beach
          and Sarasota have none (also none for 2024).
  table1  Comparison of Levies: each taxing authority's millage, rolled-back rate and taxes
          levied; all 67 counties plus a statewide file.
The directory pages need a browser, so the manifest is collected by hand (one file name has a
DOR typo: "Heranando Table 1.pdf"). Files go to data/raw/fl_rates_<year>/<kind>/.
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://floridarevenue.com/property/dataportal/Documents/PTO Data Portal/"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, default=2025)
    year = p.parse_args().year
    out = ROOT / "data" / "raw" / f"fl_rates_{year}"
    failed = []
    with open(ROOT / "manifests" / f"fl_rates_{year}.csv") as fh:
        rows = list(csv.DictReader(fh))
    for i, r in enumerate(rows, 1):
        dest = out / r["kind"] / f"{r['county']}.pdf"
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = quote(BASE + r["path"], safe=":/")
        res = subprocess.run(["curl", "-sS", "-L", "--retry", "5", "-f", "-o", str(dest), url])
        if res.returncode != 0:
            failed.append(f"{r['kind']} {r['county']}")
        print(f"[{i}/{len(rows)}] {r['kind']} {r['county']}: {'ok' if res.returncode == 0 else 'FAILED'}")
    print(f"done; {len(failed)} failed" + (f": {failed}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
