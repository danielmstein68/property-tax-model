"""Geography helpers: PUMA -> county, county -> area groups used for aging."""

import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRACT_TO_PUMA = ROOT / "data" / "raw" / "tract_to_puma_2020.txt"
TRACT_TO_PUMA_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/2020_Census_Tract_to_2020_PUMA.txt"

# Florida metro areas with their own BLS CPI series (county FIPS codes).
FL_CPI_AREAS = {
    "miami": {"086", "011", "099"},          # Miami-Dade, Broward, Palm Beach
    "tampa": {"057", "103", "101", "053"},   # Hillsborough, Pinellas, Pasco, Hernando
}


def puma_main_county(state_fips: str) -> pd.DataFrame:
    """Each PUMA's main county (the county holding most of its census tracts)."""
    if not TRACT_TO_PUMA.exists():
        TRACT_TO_PUMA.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(TRACT_TO_PUMA_URL, TRACT_TO_PUMA)
    t = pd.read_csv(TRACT_TO_PUMA, dtype=str, encoding="utf-8-sig")
    t = t[t["STATEFP"] == state_fips]
    main = (t.groupby(["PUMA5CE", "COUNTYFP"]).size().rename("tracts").reset_index()
             .sort_values("tracts", ascending=False).drop_duplicates("PUMA5CE"))
    return main.rename(columns={"PUMA5CE": "PUMA", "COUNTYFP": "county_fips"})[["PUMA", "county_fips"]]


def fl_cpi_area(county_fips: pd.Series) -> pd.Series:
    """Map Florida county FIPS to a CPI area: miami, tampa, or other_fl (South region)."""
    out = pd.Series("other_fl", index=county_fips.index)
    for area, counties in FL_CPI_AREAS.items():
        out[county_fips.isin(counties)] = area
    return out
