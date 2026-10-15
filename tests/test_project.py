import numpy as np
import pandas as pd
import pytest

from ptm.economy import Economy
from ptm.engine.assess import assess
from ptm.law import load_law
from ptm.project import lock_in_factor, project_law


def test_project_law_indexing():
    law, econ = load_law(), Economy("central")
    p = project_law(law, econ, 2030)
    cap = p.rule("soh_cap").spec["cap"]
    assert cap[2026] == 0.027                                    # known years untouched
    assert cap[2027] == pytest.approx(min(0.03, econ.rate("cpi", 2026)))
    amt = p.rule("homestead_second").spec["amount"]
    assert amt[2027] == round(26411 * (1 + econ.rate("cpi", 2026)))
    assert amt[2030] > amt[2029] > amt[2028]
    assert law.rule("soh_cap").spec["cap"].get(2027) is None    # original law not modified


def test_project_law_cpi_floor_and_cap():
    law = load_law()
    econ = Economy("central", overrides={"cpi": {"set": {2026: 0.05, 2027: -0.01}}})
    p = project_law(law, econ, 2028)
    assert p.rule("soh_cap").spec["cap"][2027] == 0.03          # capped at 3%
    assert p.rule("soh_cap").spec["cap"][2028] == -0.01         # CPI fell: cap negative
    amt = p.rule("homestead_second").spec["amount"]
    assert amt[2028] == amt[2027]                               # positive changes only


def test_portability_transfer():
    law = load_law()
    u = pd.DataFrame({"jv": [400_000.0, 400_000.0, 2_000_000.0], "av_school_prior": [200_000.0] * 3,
                      "av_nonschool_prior": [200_000.0] * 3, "homestead": [True] * 3,
                      "homestead_prior": [True] * 3, "changed_ownership": [True] * 3,
                      "portability_transfer": [0.0, 150_000.0, 900_000.0]})
    a = assess(u, law, 2027)
    assert list(a["av_school"]) == [400_000.0, 250_000.0, 1_500_000.0]   # last capped at $500k


def test_lock_in():
    f = lock_in_factor(np.array([0, 100_000, 1_000_000]), -0.0625, 0.5)
    assert list(f) == [1.0, 0.9375, 0.5]


def test_rate_ratio_rules():
    from ptm.rate_setting import rate_ratio
    g = np.array([0.95, 1.05, 1.20])
    assert list(rate_ratio("hold", g, 1.10)) == [1.0, 1.0, 1.0]
    assert rate_ratio("rolled_back", g, 1.10) == pytest.approx(1 / g)
    assert rate_ratio("keep_capped", g, 1.10) == pytest.approx([1.0, 1.0, 1.10 / 1.20])  # cut only above 110%
    with pytest.raises(ValueError):
        rate_ratio("whatever", g, 1.10)


def test_history_draws_shape_and_cap():
    from ptm.rate_setting import RateHistory
    h = RateHistory(neighbors=60)
    rng = np.random.default_rng(0)
    d = h.draw("county", np.log(np.array([0.9, 1.04, 1.25])), rng, 500)
    assert d.shape == (500, 3)
    assert (d[:, 1] > 0).mean() < 0.3                     # rate increases are uncommon in normal years
    assert np.median(d[:, 1]) == 0                         # typical county keeps its rate


def test_shock_overrides_reproducible():
    from ptm.montecarlo import shock_overrides
    a, b = shock_overrides("central", 7, 2030), shock_overrides("central", 7, 2030)
    assert a == b
    assert set(a) == {"home_value", "nonresidential_value", "cpi"}
    assert 2026 in a["cpi"]["set"] and 2030 in a["home_value"]["set"]
