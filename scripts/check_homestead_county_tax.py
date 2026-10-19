"""Check modelled homestead taxable value against official county levies (DOR Tables 1 and 2).

Usage:
    python scripts/check_homestead_county_tax.py

For each county government: official homestead dollars = 2025 levy (Table 1) x share levied on
homestead property (Table 2). Model = sum over baseline homesteads of non-school taxable value x
the county's 2025 millage. The county rate is countywide, so this tests homestead taxable values
(values, assessment gaps, exemptions) independently of tax-district assignment.
Expect a ratio a little above 1: 2026 taxable values (Save Our Homes growth, new homesteads)
against 2025 levies.
Writes data/processed/fl_rates_work/check_homestead_bcc.csv.
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.baseline import load_baseline  # noqa: E402
from ptm.millage import county_fips_by_name  # noqa: E402
from ptm.rates import parse_table1, pdf_text  # noqa: E402

COUNTY_GOV = r"BCC|Board of County|County Commission"
COUNTY_GOV_EXACT = {"Palm Beach": "Palm Beach County", "Volusia": "Volusia County General Fund", "Clay": "County Services"}
# Duval is a consolidated city-county with separate general-government levies for Baldwin, the
# Beaches and the rest, so no single countywide rate applies; it is skipped.
SKIP = {"Duval"}


def main() -> None:
    rows, failed = [], []
    for county, fips in county_fips_by_name().items():
        if county in SKIP:
            failed.append(f"{county} (skipped)")
            continue
        t1 = parse_table1(pdf_text(ROOT / "data" / "raw" / "fl_rates_2025" / "table1" / f"{county}.pdf"))
        if county in COUNTY_GOV_EXACT:
            gov = t1[t1["authority"] == COUNTY_GOV_EXACT[county]]
        else:
            gov = t1[t1["authority"].str.contains(COUNTY_GOV, case=False)
                     & ~t1["authority"].str.contains(r"\b(?:mstu|msbu|district|center)\b", case=False)]   # Clay: "BCC-Challenger Center Mstu"
        if gov.empty:
            failed.append(county)
            continue
        g = gov.iloc[0]
        lines = pdf_text(ROOT / "data" / "raw" / "fl_rates_2025" / "table2" / f"{county}.pdf").splitlines()
        line = next((l for l in lines if l.strip().startswith(g["authority"][:12]) and "%" in l), None)
        if line is None:
            failed.append(county)
            continue
        share = float(re.findall(r"(-?\d+\.\d)%", line)[0]) / 100
        rows.append({"county": county, "fips": fips, "authority": g["authority"], "millage": g["millage_2025"],
                     "levy": g["levy_2025"], "homestead_share": share})
    t = pd.DataFrame(rows)
    t["official_homestead"] = t["levy"] * t["homestead_share"]
    h = load_baseline()
    hs = h[(h["tenure"] == "owner") & (h["homestead"] == True)]  # noqa: E712
    taxable = (hs["taxable_nsd_2026"] * hs["WGTP"]).groupby(hs["county_fips_tax"]).sum()
    t["model_homestead"] = t["fips"].map(taxable) * t["millage"] / 1000
    t["ratio"] = t["model_homestead"] / t["official_homestead"]
    out = ROOT / "data" / "processed" / "fl_rates_work" / "check_homestead_bcc.csv"
    t.to_csv(out, index=False)
    print(f"counties: {len(t)} (not parsed: {failed})")
    print(f"statewide model/official: {t['model_homestead'].sum() / t['official_homestead'].sum():.3f}")
    print(t.sort_values("official_homestead", ascending=False).head(12)[["county", "ratio"]].round(3).to_string(index=False))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
