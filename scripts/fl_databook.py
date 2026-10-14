"""Download Florida DOR Ad Valorem Valuation and Tax Data Book tables (current edition).

Usage:
    python scripts/fl_databook.py

The data book's "current year" tables are overwritten each edition (preliminary in August,
final in January), so files are saved with the download date:
data/raw/fl_databook/<YYYY-MM-DD>/<name>.xlsx. Tables:
  taxable_value      all-property taxable value by county (real, personal, centrally assessed)
  new_construction   new construction just/taxable value by county, 1997 onward
  school_report      school taxable value by county
Source: https://floridarevenue.com/property/Pages/DataPortal_DataBook.aspx
"""

import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://floridarevenue.com/property/Documents/"
TABLES = ["taxable_value", "new_construction", "school_report"]


def main() -> None:
    out = ROOT / "data" / "raw" / "fl_databook" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        dest = out / f"{t}.xlsx"
        subprocess.run(["curl", "-sS", "-L", "--retry", "5", "-f", "-o", str(dest), BASE + f"{t}.xlsx"], check=True)
        print(f"{t}: {dest.stat().st_size:,} bytes")
    print(f"saved to {out}")


if __name__ == "__main__":
    main()
