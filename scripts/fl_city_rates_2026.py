"""Collect 2026 city operating millage -> inputs/fl_city_millage_2026.csv

Usage:
    python scripts/fl_city_rates_2026.py

Sources (downloaded to data/raw/fl_city_rates_2026/<county>/, collected 2026-10-14):
  - Miami-Dade Property Appraiser, "2026 and 2025 Proposed Millage Comparison" (Aug 24, 2026): every
    city's 2025 and proposed 2026 operating millage.
  - Palm Beach Property Appraiser, "2026 Proposed, Roll-Back and 2025 Final Millage Rates".
  - Manatee Property Appraiser, "2026 Final Adopted Millage Rates" (columns: adopted, proposed,
    rolled-back, prior year).
  - Lee Property Appraiser, "2026 Taxing District Millage Book (Prelim)" (rolled-back, proposed,
    previous).
  - Hand-collected rows (MANUAL) from city records and local news, each with its URL.

Status: "final" = adopted at the September final hearing; "proposed" = the TRIM maximum or
tentative rate (a final rate can only be the same or lower). Operating millage only; city debt
service levies are not included. Cities not listed are held at 2025 by the model.
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ptm.rates import pdf_text  # noqa: E402

RAW = ROOT / "data" / "raw" / "fl_city_rates_2026"
MD_URL = "https://www.miamidadepa.gov/resources-pa/library/reports/certification/2026-proposed-millage-rate-comparison.pdf"
PB_URL = "https://pbcpao.gov/pdf/taxroll/2026_Proposed_Rollback_025_Final_Millage_Rates.pdf"
MAN_URL = "https://www.manateepao.gov/data/Tax_Roll_Data/Millages/2026%20Final%20Adopted%20Millage%20Rates.pdf"
LEE_URL = "https://www.leepa.org/TaxRoll/Millage%20Books/2026%20Taxing%20District%20Millage%20Book%20Prelim.pdf"

# county, city, 2025, 2026, status, source_url, note
MANUAL = [
    ("Lee", "Fort Myers", 6.5000, 6.9000, "final",
     "https://www.gulfshorebusiness.com/lee/fort-myers-city-council-approves-property-tax-hike-for-2027/article_c7389720-7ea0-4167-9ef7-67dc6f3bcb17.html",
     "5-2 vote, Sept 2026; TRIM cap was 7.3112"),
    ("Lee", "Fort Myers Beach", 1.0294, 1.0655, "final", "https://beachtalkradionews.com/26336-2/", "adopted Sept 23, 2026"),
    ("Broward", "Fort Lauderdale", 4.1193, 4.1193, "final",
     "https://citizenportal.ai/articles/9944281/florida/broward-county/fort-lauderdale/fort-lauderdale-adopts-128-billion-fy2027-budget-commission-keeps-millage-above-rollback-herbst-votes-no", ""),
    ("Broward", "Hollywood", 7.4293, 7.4293, "proposed",
     "https://citizenportal.ai/articles/9992921/Florida/Broward-County/Hollywood-City/City-of-Hollywood-unveils-1-billion-FY2027-budget-with-flat-operating-millage", "flat"),
    ("Broward", "Davie", 5.6250, 5.3392, "final",
     "https://citizenportal.ai/articles/10036928/Florida/Broward-County/Davie/Davie-council-adopts-FY2027-millage-at-rollback-officials-say-no-tax-increase", "rolled-back rate"),
    ("Broward", "Coral Springs", 6.0232, 6.0232, "proposed",
     "https://citizenportal.ai/articles/8374008/florida/broward-county/coral-springs/coral-springs-sets-trim-keeps-millage-flat-and-schedules-sept-hearings-as-fy2027-trim-is-adopted", "flat"),
    ("Pinellas", "St Petersburg", 6.4525, 6.4525, "proposed",
     "https://stpetecatalyst.com/st-pete-holds-property-tax-rate-steady/", "tentative, unanimous; flat"),
    ("Orange", "Apopka", 4.4376, 4.6761, "proposed",
     "https://theapopkachief.com/apopka-adopts-tentative-fy27-budget-4-6761-mill-tax-rate-restores-disputed-spending/", "tentative Sept 3, 2026"),
    ("Flagler", "Palm Coast", 4.0893, 4.1387, "final",
     "https://www.observerlocalnews.com/news/2026/sep/24/palm-coast-adopts-5339-million-budget-with-41387-millage-rate/", "rolled-back rate"),
    ("Brevard", "Palm Bay", 6.7000, 6.6015, "final",
     "https://citizenportal.ai/articles/9921099/florida/brevard-county/palm-bay/palm-bay-council-sets-tentative-operating-millage-at-66015-and-debt-millage-at-09385",
     "tentative Sept 10 at rolled-back rate; final Sept 23 adopted the rolled-back rate (news.thepalmbayer.com)"),
]


def miami_dade() -> list[tuple]:
    t = pdf_text(RAW / "miami-dade" / "2026-proposed-millage-rate-comparison.pdf")
    rows = []
    for m in re.finditer(r"^(\d\d) \1 ([A-Za-z .'-]+?) (\d+\.\d{4}) (\d+\.\d{4}) ", t, re.M):
        rows.append(("Miami-Dade", m.group(2).replace("City of ", ""), float(m.group(3)), float(m.group(4)),
                     "proposed", MD_URL, "PA comparison sheet, Aug 24, 2026"))
    return rows


def palm_beach() -> list[tuple]:
    t = pdf_text(RAW / "palm-beach" / "2026_Proposed_Rollback_2025_Final.pdf")
    rows = []
    for m in re.finditer(r"^(\d\d) ([A-Za-z .]+?) (\d+\.\d{4}) (\d+\.\d{4}) (\d+\.\d{3,4}) ", t, re.M):
        name = re.sub(r"\s+", " ", m.group(2)).strip()
        if re.search(r"Debt|\(DS\)|County|SFWMD|School|F\.I\.N\.D|Children|Health|Port|DDA|NBHD|Does not|Library|District", name)                 or name == "Jupiter Inlet":  # special district (not Jupiter Inlet Colony)
            continue
        name = {"Lake Clark Shores": "Lake Clarke Shores", "Lake Worth": "Lake Worth Beach"}.get(name, name)
        rows.append(("Palm Beach", name, float(m.group(3)), float(m.group(4)), "proposed", PB_URL, "PA sheet"))
    return rows


def manatee() -> list[tuple]:
    t = pdf_text(RAW / "manatee" / "2026_Final_Adopted_Millage_Rates.pdf")
    rows = []
    for m in re.finditer(r"(City of [A-Za-z ]+?|Town of Longboat Key) (\d+\.\d{4}) (\d+\.\d{4}) (\d+\.\d{4}) (\d+\.\d{4})", t):
        name = m.group(1).replace("City of ", "").replace("Town of ", "")
        rows.append(("Manatee", name, float(m.group(5)), float(m.group(2)), "final", MAN_URL, "PA final adopted sheet"))
    return rows


def lee() -> list[tuple]:
    t = pdf_text(RAW / "lee" / "2026_Taxing_District_Millage_Book_Prelim.pdf")
    rows, seen = [], set()
    pat = r"((?:CITY|TOWN|VILLAGE) OF [A-Z .]+?)(\d{3}) AD VALOREM (\d+\.\d{4})TAXABLE\s+\w+\s+\d+ \d{4}\s+\S+\s+(\d+\.\d{4})(\d+\.\d{4})"
    for m in re.finditer(pat, t):
        name = m.group(1).strip()
        if name in seen or "DEBT" in name:
            continue
        seen.add(name)
        name = re.sub(r"^(CITY|TOWN|VILLAGE) OF ", "", name).replace(" FLORIDA", "").title()
        rows.append(("Lee", name, float(m.group(5)), float(m.group(4)), "proposed", LEE_URL, "PA preliminary millage book (TRIM maximum)"))
    return rows


def main() -> None:
    rows = miami_dade() + palm_beach() + manatee() + lee()
    manual = {(c, n) for c, n, *_ in MANUAL}
    rows = [r for r in rows if (r[0], r[1]) not in manual] + MANUAL
    d = pd.DataFrame(rows, columns=["county", "city", "mill_2025", "mill_2026", "status", "source_url", "note"])
    d = d.sort_values(["county", "city"])
    dest = ROOT / "inputs" / "fl_city_millage_2026.csv"
    d.to_csv(dest, index=False)
    print(f"wrote {dest}: {len(d)} cities ({(d.status == 'final').sum()} final), "
          f"{(d.mill_2026 != d.mill_2025).sum()} changed")


if __name__ == "__main__":
    main()
