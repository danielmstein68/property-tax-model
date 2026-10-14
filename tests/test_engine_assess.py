"""Hand-worked cases for assessment rules (Save Our Homes cap 2.7% in 2026, 2.9% in 2025)."""

import pandas as pd
import pytest

from ptm.engine.assess import assess
from ptm.law import load_law

LAW = load_law("fl")


def one(year=2026, **kw):
    base = {"jv": 0, "av_school_prior": 0, "av_nonschool_prior": 0, "homestead": False,
            "homestead_prior": False, "changed_ownership": False, "improvements": 0}
    base.update(kw)
    return assess(pd.DataFrame([base]), LAW, year).iloc[0]


def hs(**kw):
    return one(homestead=True, homestead_prior=True, **kw)


def test_homestead_capped_when_market_rises_faster():
    r = hs(jv=300_000, av_school_prior=200_000, av_nonschool_prior=200_000)
    assert r.av_school == pytest.approx(200_000 * 1.027)
    assert r.av_nonschool == r.av_school
    assert r.basis == "homestead: capped (Save Our Homes)"


def test_homestead_rises_to_just_value_when_below_cap():
    r = hs(jv=203_000, av_school_prior=200_000, av_nonschool_prior=200_000)
    assert r.av_school == 203_000


def test_recapture_when_market_falls_but_stays_above_assessed():
    # just value fell from (say) 350k to 300k but is still above last year's 200k assessed:
    # assessed still rises by the cap (Rule 12D-8.0062(5))
    r = hs(jv=300_000, av_school_prior=200_000, av_nonschool_prior=200_000)
    assert r.av_school == pytest.approx(205_400)


def test_market_falls_below_assessed():
    r = hs(jv=180_000, av_school_prior=200_000, av_nonschool_prior=200_000)
    assert r.av_school == 180_000


def test_homestead_resets_after_sale():
    r = hs(jv=400_000, av_school_prior=150_000, av_nonschool_prior=150_000, changed_ownership=True)
    assert r.av_school == 400_000 and r.basis == "homestead: reset to just value"


def test_first_homestead_year_is_just_value():
    r = one(homestead=True, homestead_prior=False, jv=350_000, av_school_prior=350_000, av_nonschool_prior=300_000)
    assert r.av_school == 350_000 and r.av_nonschool == 350_000


def test_improvements_added_at_just_value():
    r = hs(jv=500_000, av_school_prior=200_000, av_nonschool_prior=200_000, improvements=60_000)
    assert r.av_school == pytest.approx(200_000 * 1.027 + 60_000)


def test_cap_by_year():
    r25 = hs(year=2025, jv=300_000, av_school_prior=200_000, av_nonschool_prior=200_000)
    r24 = hs(year=2024, jv=300_000, av_school_prior=200_000, av_nonschool_prior=200_000)
    assert r25.av_school == pytest.approx(205_800) and r24.av_school == pytest.approx(206_000)


def test_non_homestead_school_at_just_value_nonschool_capped_10pct():
    r = one(jv=150_000, av_school_prior=140_000, av_nonschool_prior=100_000)
    assert r.av_school == 150_000
    assert r.av_nonschool == pytest.approx(110_000)
    assert r.basis == "non-homestead: capped (10%)"


def test_non_homestead_cap_not_binding():
    r = one(jv=105_000, av_school_prior=100_000, av_nonschool_prior=100_000)
    assert r.av_nonschool == 105_000


def test_non_homestead_resets_after_sale_or_losing_homestead():
    sold = one(jv=150_000, av_nonschool_prior=100_000, changed_ownership=True)
    lost = one(jv=150_000, av_nonschool_prior=90_000, homestead_prior=True)
    assert sold.av_nonschool == 150_000 and lost.av_nonschool == 150_000


def test_multi_year_homestead_path():
    # bought 2023 (assessed at just value from 2024), market +20% then +5%; caps 2.9%, 2.7%
    av = 300_000.0
    for year, jv in [(2025, 360_000), (2026, 378_000)]:
        r = hs(year=year, jv=jv, av_school_prior=av, av_nonschool_prior=av)
        av = r.av_school
    assert av == pytest.approx(300_000 * 1.029 * 1.027)
