"""Tests for the Amendment 3 example property owners (scripts/a3_examples.py): the year-by-year
engine path for each kind of owner, and how rate paths move a place's 2026 rates."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import a3_examples as ax  # noqa: E402
from ptm.economy import Economy  # noqa: E402

RATES = {"school": 6.0, "county": 5.0, "municipal": 6.0, "special": 0.0}


@pytest.fixture(scope="module")
def setup():
    econ = Economy("central")
    return econ, ax.laws(econ)


def _spec(kind="homestead", jv=600_000, ratio=1.0, place="orlando", **kw):
    return {"id": "t", "place": place, "kind": kind, "jv_2026": jv, "av_ratio_2026": ratio, "rates_2026": dict(RATES), **kw}


def test_homestead_above_250k_gets_the_full_exemption(setup):
    econ, L = setup
    s = _spec(jv=600_000, ratio=0.5)                               # assessed $300,000 in 2026
    cur, a3 = ax.taxable_path(s, L["current"], econ), ax.taxable_path(s, L["written"], econ)
    assert cur[2026] == a3[2026]                                   # nothing changes before 2027
    av28 = a3[2028]["school"] + 25_000                             # school keeps only the $25,000
    assert a3[2028]["county"] == pytest.approx(av28 - 250_000)
    assert a3[2028]["school"] == pytest.approx(cur[2028]["school"])


def test_newcomer_waits_four_years_then_matches_the_floridian(setup):
    econ, L = setup
    s = _spec(kind="pair", jv=400_000, buy_year=2027)
    new, fl = ax.taxable_path(s, L["written"], econ, newcomer=True), ax.taxable_path(s, L["written"], econ)
    assert 2027 not in new                                         # bought during 2027: first homestead year 2028
    for y in range(2028, 2032):
        assert new[y]["county"] > fl[y]["county"] + 100_000        # $50,000 instead of $250,000
    for y in range(2032, 2037):
        assert new[y]["county"] == pytest.approx(fl[y]["county"])
    struck = ax.taxable_path(s, L["struck"], econ, newcomer=True)
    assert all(struck[y]["county"] == pytest.approx(fl[y]["county"]) for y in fl)


def test_rental_at_full_value_gains_nothing_from_the_5pct_cap_when_values_grow_slowly(setup):
    econ, L = setup
    s = _spec(kind="nonhomestead", jv=250_000, ratio=1.0)
    cur, a3 = ax.taxable_path(s, L["current"], econ), ax.taxable_path(s, L["written"], econ)
    assert max(ax.growth("nonhomestead", econ, y) for y in range(2027, 2037)) < 0.05
    assert all(a3[y]["county"] == pytest.approx(cur[y]["county"]) for y in cur)


def test_capped_commercial_property_catches_up_more_slowly_under_5pct(setup):
    econ, L = setup
    s = _spec(kind="nonresidential", jv=1_000_000, ratio=0.8)
    cur, a3 = ax.taxable_path(s, L["current"], econ), ax.taxable_path(s, L["written"], econ)
    assert cur[2027]["county"] == pytest.approx(800_000 * 1.10)    # 10% cap now
    assert a3[2027]["county"] == pytest.approx(800_000 * 1.05)     # 5% under the amendment
    assert a3[2027]["school"] == cur[2027]["school"]               # school at just value either way


def test_bills_use_2026_rates_moved_by_the_path():
    s = _spec()
    taxable = {2026: {"school": 100_000, "county": 100_000, "municipal": 100_000, "special": 0},
               2027: {"school": 100_000, "county": 100_000, "municipal": 100_000, "special": 0}}
    fips = ax.PLACES["orlando"][0]
    paths = {"2027": {"county": {fips: 1.2}, "city": {f"{fips}|orlando": 1.5}, "school": {fips: 5.0}}}
    b = ax.bills(s, taxable, paths)
    assert b[2026] == {"school": 600, "nonschool": 1100, "total": 1700}
    assert b[2027] == {"school": 500, "nonschool": 600 + 900, "total": 2000}
