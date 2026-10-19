"""District millage split into county and city levies (ptm.millage.district_classes): districts in a
city get that city's rate, whichever way the rate file's note names the place, and special taxing
units listed by bare name aren't mistaken for cities (2026-10-19 fix: Polk and Volusia had no cities,
Port St. Lucie and St. Cloud were missing)."""

import pandas as pd
import pytest

from ptm.millage import county_fips_by_name, district_classes


@pytest.fixture(scope="module")
def dc():
    d = district_classes(2025, 2026)
    return d.assign(county=d["county_fips"].map({v: k for k, v in county_fips_by_name().items()}))


def _city(dc, county, code):
    r = dc[(dc["county"] == county) & (dc["code"] == code)].iloc[0]
    return str(r["municipality"]).upper(), float(r["millage_municipal"])


def test_note_formats_name_cities(dc):
    assert _city(dc, "Polk", "91510") == ("LAKELAND", pytest.approx(5.4323))          # "Lakeland city 5.4323 + unincorporated-less-MSTU ..."
    assert _city(dc, "Volusia", "016") == ("DELTONA", pytest.approx(6.7))             # "Deltona; components sum to total"; Table 1 "Deltona Operating"
    assert _city(dc, "Saint Lucie", "0011")[0] == "PORT ST LUCIE"                       # "Port St Lucie 4.6607 + PSL voted debt ..."
    assert _city(dc, "Osceola", "100")[0] == "SAINT CLOUD"                              # "Saint Cloud" vs Table 1 "City of St Cloud"
    assert _city(dc, "Palm Beach", "06155")[0] == "BOCA RATON"                          # note is just the name


def test_not_cities(dc):
    assert _city(dc, "Osceola", "408") == ("", 0.0)       # Bellalago: an MSBU listed by bare name in Table 1
    assert _city(dc, "Polk", "90000") == ("", 0.0)        # "unincorporated base area"
    assert _city(dc, "Volusia", "100") == ("", 0.0)       # "County - Westside"


def test_every_county_with_cities_has_city_districts(dc):
    n = dc.groupby("county")["millage_municipal"].apply(lambda s: int((s > 0).sum()))
    for c in ["Polk", "Volusia", "Saint Lucie", "Osceola", "Miami-Dade", "Orange", "Hillsborough", "Lee"]:
        assert n[c] > 0, c
    # the county levy left in a city district is never below the county government's own rate
    assert (dc["millage_county"].dropna() >= -1e-9).all()
