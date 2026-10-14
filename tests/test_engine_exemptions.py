"""Hand-worked cases for the exemption engine against the Florida spec (2026 values unless noted).

Second homestead exemption: $26,411 in 2026 on assessed value above $50,000 (non-school only).
"""

import pandas as pd
import pytest

from ptm.engine import apply_exemptions
from ptm.law import load_law

LAW = load_law("fl")
CLASSES = ["school", "county", "municipal", "special"]


def unit(av, av_school=None, **flags):
    row = {f"av_{c}": av for c in CLASSES}
    if av_school is not None:
        row["av_school"] = av_school
    row.update(flags)
    return row


def run(rows, year=2026):
    return apply_exemptions(pd.DataFrame(rows), LAW, year)


def taxable(res, i=0):
    return {c: round(res.loc[i, f"taxable_{c}"], 2) for c in CLASSES}


def test_homestead_100k():
    # school: 100,000 - 25,000; others: 100,000 - 25,000 - 26,411
    t = taxable(run([unit(100_000, homestead=True)]))
    assert t == {"school": 75_000, "county": 48_589, "municipal": 48_589, "special": 48_589}


def test_homestead_inside_second_band():
    # 60,000: second band takes 60,000 - 50,000 = 10,000 (non-school)
    t = taxable(run([unit(60_000, homestead=True)]))
    assert t == {"school": 35_000, "county": 25_000, "municipal": 25_000, "special": 25_000}


def test_homestead_below_first_exemption_is_zero():
    t = taxable(run([unit(20_000, homestead=True)]))
    assert t == {c: 0 for c in CLASSES}


def test_second_band_amount_by_year():
    # 2025 amount is 25,722; 2024 is 25,000
    assert taxable(run([unit(200_000, homestead=True)], 2025))["county"] == 200_000 - 25_000 - 25_722
    assert taxable(run([unit(200_000, homestead=True)], 2024))["county"] == 200_000 - 50_000


def test_non_homestead_gets_no_homestead_exemption():
    # non-homestead: school assessed at just value, others capped (passed in as given)
    t = taxable(run([unit(180_000, av_school=200_000, homestead=False)]))
    assert t == {"school": 200_000, "county": 180_000, "municipal": 180_000, "special": 180_000}


def test_veteran_total_exemption_zeroes_all_levies():
    t = taxable(run([unit(400_000, homestead=True, ex_vet_total=True)]))
    assert t == {c: 0 for c in CLASSES}


def test_long_term_senior_county_only():
    # total exemption for county levies only; city and school still taxed
    t = taxable(run([unit(150_000, homestead=True, ex_senior_longterm=True)]))
    assert t == {"school": 125_000, "county": 0, "municipal": 98_589, "special": 98_589}


def test_low_income_senior_county_amount_and_cap():
    # county ordinance amount 45,000 (county levies only); amounts above 50,000 are capped
    t = taxable(run([unit(150_000, homestead=True, ex_senior_lowinc=True, ex_senior_amount=45_000),
                     unit(150_000, homestead=True, ex_senior_lowinc=True, ex_senior_amount=80_000)]))
    assert t["county"] == 150_000 - 25_000 - 26_411 - 45_000
    assert t["municipal"] == 150_000 - 25_000 - 26_411
    t2 = taxable(run([unit(150_000, homestead=True, ex_senior_lowinc=True, ex_senior_amount=80_000)]))
    assert t2["county"] == 150_000 - 25_000 - 26_411 - 50_000


def test_five_thousand_exemptions_count_and_all_levies():
    # a widow ($5,000) and two disabled ex-service exemptions (2 x $5,000); applies to school too
    t = taxable(run([unit(100_000, homestead=True, ex_widow_blind_disabled=1, ex_disabled_exservice=2)]))
    assert t["school"] == 100_000 - 25_000 - 15_000
    assert t["county"] == 100_000 - 25_000 - 26_411 - 15_000


def test_five_thousand_exemption_on_non_homestead():
    t = taxable(run([unit(100_000, homestead=False, ex_widow_blind_disabled=1)]))
    assert t == {c: 95_000 for c in CLASSES}


def test_floor_at_zero():
    t = taxable(run([unit(60_000, homestead=True, ex_senior_lowinc=True, ex_senior_amount=50_000)]))
    assert t["county"] == 0 and t["school"] == 35_000


def test_veterans_discount_is_a_percentage_applied_last_per_levy():
    # 30% discount on what's left after the homestead exemptions, separately for each levy
    t = taxable(run([unit(200_000, homestead=True, ex_vet_discount=True, ex_vet_discount_share=0.30)]))
    assert t["school"] == pytest.approx((200_000 - 25_000) * 0.70)
    assert t["county"] == pytest.approx((200_000 - 25_000 - 26_411) * 0.70)


def test_discount_after_local_option_exemption():
    # s. 196.082(6): deduct all other exemptions (incl. local option) first, then the discount
    t = taxable(run([unit(200_000, homestead=True, ex_senior_lowinc=True, ex_senior_amount=50_000,
                          ex_vet_discount=True, ex_vet_discount_share=0.50)]))
    assert t["county"] == pytest.approx((200_000 - 25_000 - 26_411 - 50_000) * 0.50)
    assert t["municipal"] == pytest.approx((200_000 - 25_000 - 26_411) * 0.50)


def test_granny_flat_limited_to_20_percent():
    t = taxable(run([unit(100_000, homestead=True, ex_granny_flat=True, ex_granny_amount=40_000)]))
    assert t["school"] == 100_000 - 25_000 - 20_000


def test_missing_columns_are_reported_not_fatal():
    res = run([unit(100_000, homestead=True)])
    assert "ex_vet_total" in res.attrs["missing"]
