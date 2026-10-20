"""Download the Texas model's public data -> data/raw/tx_*  (sources: docs/research/tx_data_sources.md)

Usage:
    python scripts/tx_download.py            # everything not yet downloaded
    python scripts/tx_download.py rolls      # only appraisal district rolls
    python scripts/tx_download.py state      # only statewide files (Comptroller, FHFA, Census)
    python scripts/tx_download.py tarrant    # one appraisal district (run several at once: servers are slow)

Each appraisal district's files go in their own folder, data/raw/tx_rolls/<district>/, and are left
zipped (ptm.tx.rolls reads them). Existing files are skipped. Socrata tables (Collin, Williamson) are
paged through the API into CSV. Large files take a while: about 3.5 GB in all.
Not covered (need a person): Bexar and Hidalgo (records requests), Denton and Montgomery (checked by
hand), Brazoria (pCloud links).
"""

import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
DCAD = "https://www.dallascad.org/ViewPDFs.aspx?type=3&id=%5C%5CDCAD.ORG%5CWEB%5CWEBDATA%5CWEBFORMS%5CDATA%20PRODUCTS%5C"
TCAD = "https://traviscad.org/wp-content/largefiles/"

ROLLS = {
    "harris": [f"https://download.hcad.org/data/CAMA/2026/{f}" for f in
               ["Real_acct_owner.zip", "Real_jur_exempt.zip", "Real_building_land.zip", "Code_description_real.zip"]]
              + ["https://hcad.org/assets/uploads/pdf/pdataCodebook.pdf"],
    "dallas": [(DCAD + "DCAD2026_CERTIFIED_07232026.zip", "DCAD2026_CERTIFIED_07232026.zip")],
    "tarrant": ["https://www.tad.org/content/data-download/000_Tarrant_All_Taxing_Units.zip"],
    "travis": [(TCAD + "2026%20Certified%20Appraisal%20Export%20Supp%200_07182026.zip", "2026_certified_export_supp0.zip"),
               (TCAD + "Website_Legacy8.0.33-AppraisalExportLayout_06182026.zip", "layout_8.0.33.zip")],
    "fort_bend": ["https://www.fbcad.org/wp-content/uploads/2026/08/2026_07_07_1746-Orion-2026-Certified-Export-Redacted.zip",
                  "https://www.fbcad.org/wp-content/uploads/2026/07/PropertyData-Post2026Cert-Redacted.zip"],
    "el_paso": ["https://export.epcad.org/datasets/2026_Certified_Export_Files.zip",
                "https://export.epcad.org/datasets/Appraisal%20Export%20Layout%20-%208.0.34.zip"],
    "galveston": ["https://galvestoncad.org/wp-content/uploads/2026/08/2026-CERTIFIED-ROLL-WEB-EXPORT-W-EXPORT-LAYOUT.zip"],
    "bell": ["https://bellcad.org/wp-content/uploads/2019/06/2026-Bell-County-Certified-Export-3.zip",
             "https://bellcad.org/wp-content/uploads/2026/02/Appraisal-Export-Layout-8.0.33.xlsx"],
}
SOCRATA = {   # district: [(host, dataset id, file name)]
    "collin": [("data.texas.gov", "5tkr-3759", "collin_2026_appraisal.csv"), ("data.texas.gov", "c922-rc4c", "collin_partial_exemptions.csv"),
               ("data.texas.gov", "kwi9-9pmz", "collin_entities.csv"), ("data.texas.gov", "fre7-8m55", "collin_state_codes.csv")],
    "williamson": [("data.wcad.org", "yeqp-u7bx", "wcad_asmt_certified.csv"), ("data.wcad.org", "nbn7-h4pp", "wcad_exemptions.csv"),
                   ("data.wcad.org", "ai3c-c9pf", "wcad_property_certified.csv"), ("data.wcad.org", "2huh-jk3y", "wcad_improvements_certified.csv")],
}
CPA = "https://comptroller.texas.gov/taxes/property-tax/docs/"
STATE = {
    "tx_cpa": [CPA + f for f in ["2025-final-isd-worksheet-export-detail.xlsx", "2024-final-isd-worksheet-export-detail.xlsx",
                                 "2025-preliminary-isd-worksheet-export-detail.xlsx", "2025-final-isd-self-report-export-detail.xlsx",
                                 "2025-city-rates-levies.xlsx", "2025-county-rates-levies.xlsx", "2025-special-district-rates-levies.xlsx"]],
    "fhfa": ["https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_state.csv",
             "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_metro.csv",
             "https://www.fhfa.gov/hpi/download/annual/hpi_at_county.xlsx"],
    "tx_census": ["https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST48_TX.zip",
                  "https://www2.census.gov/geo/docs/reference/codes2020/cou/st48_tx_cou2020.txt"],
    "tx_forecast": ["https://comptroller.texas.gov/transparency/reports/certification-revenue-estimate/2026-27/docs/cre-2026-27-data.xlsx",
                    "https://comptroller.texas.gov/transparency/reports/biennial-revenue-estimate/2026-27/docs/bre-2026-27.xlsx"],
}


def get(url: str, dest: Path, tries: int = 30) -> None:
    """Download with resume: a dropped connection continues from the partial file (HTTP Range), and a
    file only counts as done when its size matches the server's Content-Length (the home connection
    drops mid-file, and urllib sometimes ends a read early without an error)."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  have {dest.name}")
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    total = None
    for k in range(tries):
        have = tmp.stat().st_size if tmp.exists() else 0
        try:
            hdr = {"User-Agent": UA}
            if have:
                hdr["Range"] = f"bytes={have}-"
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=60) as r:
                if have and r.status != 206:     # server ignored the range: start again
                    have = 0
                n = r.headers.get("Content-Length")
                if n is not None:
                    total = have + int(n)
                with open(tmp, "ab" if have else "wb") as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
            size = tmp.stat().st_size
            if total is None or size >= total:
                tmp.replace(dest)
                print(f"  got {dest.name} ({size / 1e6:.0f} MB)")
                return
            print(f"  short {dest.name}: {size / 1e6:.0f} of {total / 1e6:.0f} MB, resuming")
        except Exception as e:   # network blips: resume after a pause
            print(f"  retry {k + 1} {dest.name} at {have / 1e6:.0f} MB: {e}")
            time.sleep(min(10 * (k + 1), 120))
    raise SystemExit(f"failed: {url}")


def socrata(host: str, ds: str, dest: Path, page: int = 50000) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  have {dest.name}")
        return
    tmp = dest.with_suffix(".part")
    off, rows = 0, 0
    with open(tmp, "wb") as f:
        while True:
            q = urllib.parse.urlencode({"$limit": page, "$offset": off, "$order": ":id"})
            for k in range(30):
                try:
                    req = urllib.request.Request(f"https://{host}/resource/{ds}.csv?{q}", headers={"User-Agent": UA})
                    body = urllib.request.urlopen(req, timeout=180).read()
                    break
                except Exception as e:
                    print(f"  retry {ds} @{off}: {e}")
                    time.sleep(min(10 * (k + 1), 120))
            else:
                raise SystemExit(f"failed: {host}/{ds}")
            lines = body.split(b"\n", 1)
            if off > 0:   # drop the repeated header
                body = lines[1] if len(lines) > 1 else b""
            n = body.count(b"\n") - (1 if off == 0 else 0)
            f.write(body)
            rows += max(n, 0)
            if n < page:
                break
            off += page
    tmp.replace(dest)
    print(f"  got {dest.name} ({rows:,} rows)")


def main(which: str = "all") -> None:
    if which in ("all", "state"):
        for folder, urls in STATE.items():
            print(folder)
            (RAW / folder).mkdir(parents=True, exist_ok=True)
            for u in urls:
                get(u, RAW / folder / urllib.parse.unquote(u.rsplit("/", 1)[1]))
    if which in ROLLS or which in SOCRATA:
        ROLLS_, SOC_ = {k: v for k, v in ROLLS.items() if k == which}, {k: v for k, v in SOCRATA.items() if k == which}
    else:
        ROLLS_, SOC_ = ROLLS, SOCRATA
    if which in ("all", "rolls") or which in ROLLS or which in SOCRATA:
        for cad, items in ROLLS_.items():
            print(cad)
            d = RAW / "tx_rolls" / cad
            d.mkdir(parents=True, exist_ok=True)
            for it in items:
                url, name = it if isinstance(it, tuple) else (it, urllib.parse.unquote(it.rsplit("/", 1)[1]))
                get(url, d / name)
        for cad, items in SOC_.items():
            print(cad)
            d = RAW / "tx_rolls" / cad
            d.mkdir(parents=True, exist_ok=True)
            for host, ds, name in items:
                socrata(host, ds, d / name)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
