"""Tests for the policy features added 2026-10-15/16: Amendment 3's exemption and new-resident rule,
non-homestead cap blocks in local tax bases, the 10-mill cap and state offsets in the revenue-neutral
mode, and the behavioural responses (take-up, residency switch)."""

import numpy as np
import pandas as pd
import pytest

from ptm.economy import Economy
from ptm.engine.exemptions import apply_exemptions
from ptm.law import load_law
from ptm.policy import apply_policy, load_policy
from ptm.project import Projection, claim_probability, fc_offset_value, project_law
from ptm.rate_setting import RateSetter

A3 = "inputs/policies/amendment3.yaml"
INPUT = "data/processed/projection_input_2026.parquet"


def _units(av, waiting=0):
    u = pd.DataFrame({f"av_{c}": [float(av)] for c in ["school", "county", "municipal", "special"]})
    return u.assign(homestead=True, new_resident_waiting=waiting)


# --- Amendment 3 exemption -------------------------------------------------------------------------
def test_amendment3_exemption_amounts():
    law = apply_policy(load_law(), load_policy(A3))
    resident = apply_exemptions(_units(300_000), law, 2028)
    assert resident["taxable_school"][0] == 275_000            # school keeps the $25,000 exemption
    assert resident["taxable_county"][0] == 50_000             # non-school: first $250,000 exempt
    newcomer = apply_exemptions(_units(300_000, waiting=1), law, 2028)
    assert newcomer["taxable_county"][0] == 250_000            # first $50,000 while waiting
    small = apply_exemptions(_units(120_000), law, 2027)
    assert small["taxable_county"][0] == 0                     # $150,000 in 2027 covers it all
    current = apply_exemptions(_units(300_000), load_law(), 2026)
    assert current["taxable_county"][0] == 300_000 - 25_000 - 26_411   # current law unchanged


def test_amendment3_schedule_indexes_from_2029():
    law = project_law(apply_policy(load_law(), load_policy(A3)), Economy("central"), 2030)
    amt = law.rule("homestead_nonschool_total").spec["amount"]
    assert amt[2027] == 150_000 and amt[2028] == 250_000
    assert amt[2030] >= amt[2029] >= 250_000                    # CPI, positive changes only
    assert law.rule("homestead_new_resident").spec["waiting_years"][2027] == 4
    assert load_law().rule("homestead_new_resident").get("waiting_years", 2027) == 0   # none in current law


# --- non-homestead cap blocks -----------------------------------------------------------------------
def _setter_with_blocks():
    rs = RateSetter.__new__(RateSetter)
    rs.blocks = {"nh": {"jc": np.array([100.0]), "ac": np.array([80.0]), "ju": np.array([50.0]),
                        "au": np.array([50.0]), "sold": np.array([0.0])}}
    return rs


def test_cap_blocks_follow_the_cap():
    rs = _setter_with_blocks()
    g = rs._capped_growth("nh", 1.03, 0.05)
    b = rs.blocks["nh"]
    assert b["ac"][0] == pytest.approx(84.0)                     # capped block: +5%
    assert b["au"][0] == pytest.approx(51.5)                     # at just value: follows value growth
    assert g[0] == pytest.approx((84 + 51.5) / 130)
    rs10 = _setter_with_blocks()
    rs10._capped_growth("nh", 1.03, 0.10)
    assert rs10.blocks["nh"]["ac"][0] == pytest.approx(88.0)     # a 10% cap catches up faster


def test_cap_blocks_never_exceed_just_value_and_sales_reset():
    rs = _setter_with_blocks()
    rs.blocks["nh"]["sold"] = np.array([0.5])
    rs._capped_growth("nh", 1.00, 0.50)
    b = rs.blocks["nh"]
    assert b["ac"][0] <= b["jc"][0] + 1e-9                        # never above just value
    rs2 = _setter_with_blocks()
    rs2.blocks["nh"]["sold"] = np.array([0.5])
    rs2._capped_growth("nh", 1.0, 0.0)
    assert rs2.blocks["nh"]["ac"][0] == pytest.approx(0.5 * 100 + 0.5 * 80)   # half reset to just value


# --- 10-mill cap and state offsets ------------------------------------------------------------------
def test_millage_cap_limits_general_and_city_levies():
    p = Projection.__new__(Projection)
    p.millage_cap = 10.0
    p.general_2026 = np.array([6.0, 9.5, 11.0])      # the last is already above 10
    p.general_share = np.array([1.0, 1.0, 1.0])
    p.city_rate_2026 = np.array([5.0, 9.0])
    bp = {"county": np.ones((1, 3)), "city": np.ones((1, 2))}
    rho_c, rho_y = p._cap_ratios(np.array([1.5, 1.5, 1.5]), np.array([1.5, 1.5]), bp)
    assert rho_c[0] == pytest.approx(1.5)                        # 9 mills: under the cap
    assert rho_c[1] == pytest.approx(10 / 9.5)                   # stops at 10
    assert rho_c[2] == pytest.approx(1.0)                        # already above 10: stays
    assert rho_y[1] == pytest.approx(10 / 9.0)
    p.general_share = np.array([0.5, 0.5, 0.5])                  # other county units rise in full
    rho_c, _ = p._cap_ratios(np.array([1.5, 1.5, 1.5]), np.array([1.5, 1.5]), bp)
    assert rho_c[1] == pytest.approx(0.5 * 10 / 9.5 + 0.5 * 1.5)


def test_fc_offset_value_formula():
    b, pol = np.array([100.0, 100.0, 100.0]), np.array([80.0, 80.0, 120.0])
    e = fc_offset_value(b, pol, np.array([1.0, 1.25, 1.0]), 0.95, np.array([True, True, True]))
    assert e[0] == pytest.approx(0.95 * 20)                      # 95% of the lost value
    assert e[1] == pytest.approx(0.95 * 20 / 1.25)               # lesser of base-year and current rate
    assert e[2] == 0                                             # no loss, no offset
    assert fc_offset_value(b, pol, np.ones(3), 0.95, np.array([False] * 3)).sum() == 0


# --- behavioural responses --------------------------------------------------------------------------
def test_claim_probability_shape():
    assert claim_probability(np.array([2500.0]), 0.20, 2500)[0] == pytest.approx(0.20)
    p = claim_probability(np.array([-100.0, 0.0, 600.0, 2500.0, 10000.0]), 0.20, 2500)
    assert p[0] == 0 and p[1] == 0
    assert 0 < p[2] < p[3] < p[4] < 1


@pytest.fixture(scope="module")
def runs():
    """Current law and Amendment 3 (with and without responses), 2026-2029, no rate response."""
    from ptm.compare import _run
    b = pd.read_parquet(INPUT)
    base = _run(b, "central", 2026, load_law(), 2029)
    law = apply_policy(load_law(), load_policy(A3))
    beh = _run(b, "central", 2026, law, 2029, rate_replay=base.rates.paths)
    static = _run(b, "central", 2026, law, 2029, rate_replay=base.rates.paths, behaviour=False)
    return base, beh, static


def test_no_responses_under_current_law(runs):
    base, _, _ = runs
    assert base.summary["new_claimants"].max() == 0
    assert base.summary["second_homes_switched"].max() == 0
    assert base.summary["homestead_new_resident_share"].max() == 0


def test_amendment3_responses(runs):
    _, beh, static = runs
    assert beh.summary.loc[2029, "new_claimants"] > 0 and beh.summary.loc[2029, "second_homes_switched"] > 0
    assert static.summary["new_claimants"].max() == 0
    assert beh.summary.loc[2029, "tax_total"] < static.summary.loc[2029, "tax_total"]       # owners pay less
    # taking up the exemption shows in owners' tax; tax on other property doesn't rise with it
    assert beh.summary.loc[2029, "nonowner_tax_nonschool"] <= static.summary.loc[2029, "nonowner_tax_nonschool"] + 1e6
    assert beh.summary.loc[2029, "homestead_new_resident_share"] > 0                      # newcomers wait


def test_portability_limit_follows_the_law():
    from ptm.compare import compare
    r = compare({"name": "no limit", "changes": [{"rule": "portability", "key": "max_transfer", "value": 1e9, "from": 2027}]},
                end_year=2028, response="none")
    assert r["changes"].loc[2028, "tax_total"] < 0                                         # raising the limit helps movers
