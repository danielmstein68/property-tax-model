"""Download an ACS PUMS state file and the matching data dictionary.

Usage:
    python scripts/download_pums.py --state fl --year 2024
    python scripts/download_pums.py --state oh --year 2024 --period 5-Year

Files land in data/raw/pums_<year>_<1yr|5yr>/ and are unzipped there.
The data dictionary goes to data/raw/PUMS_Data_Dictionary_<year>.csv.
"""

import argparse
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www2.census.gov/programs-surveys/acs"
ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"


def download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"exists, skipping: {dest.name}")
        return
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, dest)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True, help="two-letter state code, e.g. fl")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--period", default="1-Year", choices=["1-Year", "5-Year"])
    p.add_argument("--person", action="store_true", help="also download the person file")
    args = p.parse_args()

    st = args.state.lower()
    tag = "1yr" if args.period == "1-Year" else "5yr"
    out = ROOT / f"pums_{args.year}_{tag}"
    out.mkdir(parents=True, exist_ok=True)

    kinds = ["h", "p"] if args.person else ["h"]
    for kind in kinds:
        name = f"csv_{kind}{st}.zip"
        zpath = out / name
        download(f"{BASE}/data/pums/{args.year}/{args.period}/{name}", zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(out)

    download(f"{BASE}/tech_docs/pums/data_dict/PUMS_Data_Dictionary_{args.year}.csv",
             ROOT / f"PUMS_Data_Dictionary_{args.year}.csv")
    print(f"done: {out}")


if __name__ == "__main__":
    main()
