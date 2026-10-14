"""The year-step: assessment + exemptions + tax together, and carrying state across years."""

import pandas as pd
import pytest

from ptm.engine.step import carry_forward, step
from ptm.law import load_law

LAW = load_law("fl")
MILLS = {"millage_school": 6.0, "millage_county": 5.0, "millage_municipal": 4.0, "millage_special": 1.0}


def units(**kw):
    base = {"jv": 300_000, "av_school_prior": 200_000, "av_nonschool_prior": 200_000, "homestead": True,
            "homestead_prior": True, "changed_ownership": False, "improvements": 0, **MILLS}
    base.update(kw)
    return pd.DataFrame([base])


def test_one_year_homestead_tax_by_hand():
    r = step(units(), LAW, 2026).iloc[0]
    av = 200_000 * 1.027                                  # Save Our Homes cap
    assert r.av_school == pytest.approx(av)
    assert r.taxable_school == pytest.approx(av - 25_000)
    assert r.taxable_county == pytest.approx(av - 25_000 - 26_411)
    expected = (av - 25_000) * 6 / 1000 + (av - 51_411) * (5 + 4 + 1) / 1000
    assert r.tax_total == pytest.approx(expected)


def test_non_homestead_tax_by_hand():
    r = step(units(homestead=False, homestead_prior=False, av_school_prior=280_000), LAW, 2026).iloc[0]
    assert r.taxable_school == 300_000                    # school at just value, no exemptions
    assert r.taxable_county == pytest.approx(220_000)     # 10% cap
    assert r.tax_total == pytest.approx(300_000 * 6 / 1000 + 220_000 * 10 / 1000)


def test_no_rates_means_no_tax_columns():
    u = units().drop(columns=list(MILLS))
    assert "tax_total" not in step(u, LAW, 2026)


def test_homestead_portion_share():
    # duplex: owner's unit is half the property; exemptions measured on that half
    r = step(units(jv=100_000, av_school_prior=100_000, av_nonschool_prior=100_000,
                   homestead_portion_share=0.5), LAW, 2026).iloc[0]
    # homestead part 50,000: first 25,000; second band on 50,000 -> 0
    assert r.taxable_school == pytest.approx(100_000 - 25_000)
    assert r.taxable_county == pytest.approx(100_000 - 25_000)


def test_three_year_path_with_sale():
    # 2024 assessed 200k (jv 300k); 2025 jv 330k -> capped; 2026 sold -> reset to jv 340k
    u = units(jv=330_000)
    r25 = step(u, LAW, 2025)
    assert r25.av_school.iloc[0] == pytest.approx(200_000 * 1.029)
    u = carry_forward(u, r25)
    u["jv"], u["changed_ownership"] = 340_000, True
    r26 = step(u, LAW, 2026)
    assert r26.av_school.iloc[0] == 340_000
    assert r26.basis.iloc[0] == "homestead: reset to just value"


def test_carry_forward_clears_events():
    u = units(changed_ownership=True, improvements=10_000)
    nxt = carry_forward(u, step(u, LAW, 2026))
    assert not nxt.changed_ownership.iloc[0] and nxt.improvements.iloc[0] == 0
    assert nxt.av_school_prior.iloc[0] == 300_000 and nxt.homestead_prior.iloc[0]
