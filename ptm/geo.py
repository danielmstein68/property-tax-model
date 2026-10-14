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


def fl_dor_to_fips(co_no: pd.Series) -> pd.Series:
    """Florida DOR county number (11-77, alphabetical) -> county FIPS (3 digits).

    Both run alphabetically, so FIPS = 2 x (DOR - 11) + 1, except Miami-Dade (DOR 23), whose
    FIPS changed from 025 to 086 in 1997.
    """
    n = pd.to_numeric(co_no)
    fips = (2 * (n - 11) + 1).astype(int).astype(str).str.zfill(3)
    return fips.where(n != 23, "086")


def fl_parcel_puma(parcels: pd.DataFrame) -> pd.Series:
    """PUMA for each Florida parcel from CENSUS_BK (block group -> tract -> PUMA).

    Returns NA where CENSUS_BK doesn't match a 2020 tract. Some counties use other formats
    (scientific notation, extra digits, 2010 tract codes); callers should allocate those
    parcels within their county (see fl_dor_to_fips).
    """
    if not TRACT_TO_PUMA.exists():
        puma_main_county("12")  # downloads the file
    t = pd.read_csv(TRACT_TO_PUMA, dtype=str, encoding="utf-8-sig")
    t = t[t["STATEFP"] == "12"]
    lookup = dict(zip(t["STATEFP"] + t["COUNTYFP"] + t["TRACTCE"], t["PUMA5CE"]))
    return parcels["CENSUS_BK"].str[:11].map(lookup)


def fl_parcel_counts_by_puma(parcels: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Sum `cols` over Florida parcels by PUMA.

    Parcels whose CENSUS_BK doesn't match a 2020 tract are spread over their county's PUMAs in
    proportion to the matched parcels (equally if the county has none matched).
    Needs CO_NO and CENSUS_BK. Returns one row per PUMA.
    """
    p = parcels.copy()
    p["PUMA"] = fl_parcel_puma(p)
    p["county_fips"] = fl_dor_to_fips(p["CO_NO"])
    matched = p[p["PUMA"].notna()].groupby(["county_fips", "PUMA"])[cols].sum()
    unmatched = p[p["PUMA"].isna()].groupby("county_fips")[cols].sum()
    pm = puma_main_county("12")
    extra = []
    for fips, row in unmatched.iterrows():
        pumas = pm.loc[pm["county_fips"] == fips, "PUMA"].tolist()
        m = matched.loc[fips] if fips in matched.index.get_level_values(0) else None
        for col in cols:
            if m is not None and m[col].sum() > 0:
                share = m[col] / m[col].sum()
            else:
                share = pd.Series(1 / len(pumas), index=pumas) if pumas else pd.Series(dtype=float)
            for puma, s in share.items():
                extra.append({"PUMA": puma, col: row[col] * s})
    out = pd.concat([matched.reset_index(), pd.DataFrame(extra)]).fillna(0)
    return out.groupby("PUMA")[cols].sum().reset_index()


def county_groups(state_fips: str = "12") -> pd.DataFrame:
    """Group counties that share PUMAs, so PUMS (by PUMA) and the roll (by county) cover the
    same areas. Large counties with their own PUMAs are their own group; small counties that
    share a PUMA are grouped. Returns county_fips, PUMA, area (group id = smallest county FIPS)
    and county_area (the county's own group).

    A county that also has a PUMA entirely its own (Miami-Dade, St. Johns) is not merged through a
    PUMA it shares with a small county (Monroe, Putnam): the shared PUMA goes to the small
    county's area, and the big county's parcels in those tracts are assigned by tract
    (parcel_area). Otherwise Monroe was calibrated with Miami-Dade's values and assessment gaps
    (model homestead tax 31% below the roll; fixed 2026-10-14).
    """
    if not TRACT_TO_PUMA.exists():
        puma_main_county(state_fips)
    t = pd.read_csv(TRACT_TO_PUMA, dtype=str, encoding="utf-8-sig")
    t = t[t["STATEFP"] == state_fips][["COUNTYFP", "PUMA5CE"]].drop_duplicates()
    # counties with at least one PUMA entirely their own
    single = t.groupby("PUMA5CE")["COUNTYFP"].nunique().loc[lambda n: n == 1].index
    has_own = set(t.loc[t["PUMA5CE"].isin(single), "COUNTYFP"])
    parent = {c: c for c in t["COUNTYFP"]}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    linked = {}
    for puma, cs in t.groupby("PUMA5CE")["COUNTYFP"]:
        cs = sorted(cs)
        small = [c for c in cs if c not in has_own]
        link = small if small else cs
        linked[puma] = link
        for c in link[1:]:
            a, b = find(link[0]), find(c)
            if a != b:
                parent[max(a, b)] = min(a, b)
    t["area"] = t["PUMA5CE"].map(lambda pu: find(linked[pu][0]))
    t["county_area"] = t["COUNTYFP"].map(find)
    return t.rename(columns={"COUNTYFP": "county_fips", "PUMA5CE": "PUMA"})


def parcel_area(parcels: pd.DataFrame) -> pd.Series:
    """county_groups area for each Florida parcel (needs CO_NO and CENSUS_BK): the county's own
    area, except parcels of a split county lying in a PUMA assigned to another area."""
    g = county_groups()
    fips = fl_dor_to_fips(parcels["CO_NO"])
    area = fips.map(g.drop_duplicates("county_fips").set_index("county_fips")["county_area"])
    split = set(g.loc[g["area"] != g["county_area"], "county_fips"])
    in_split = fips.isin(split)
    if in_split.any():
        puma_area = g.drop_duplicates("PUMA").set_index("PUMA")["area"]
        by_tract = fl_parcel_puma(parcels.loc[in_split]).map(puma_area)
        area.loc[in_split] = by_tract.fillna(area.loc[in_split])
    return area


def fl_cpi_area(county_fips: pd.Series) -> pd.Series:
    """Map Florida county FIPS to a CPI area: miami, tampa, or other_fl (South region)."""
    out = pd.Series("other_fl", index=county_fips.index)
    for area, counties in FL_CPI_AREAS.items():
        out[county_fips.isin(counties)] = area
    return out
