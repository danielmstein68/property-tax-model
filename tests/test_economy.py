import pandas as pd
import pytest

from ptm.economy import Economy


def test_central_follows_rec_then_eases():
    e = Economy("central")
    paths = pd.read_csv("inputs/fl_economy_paths.csv")
    rec = paths[(paths.variable == "appreciation_residential") & (paths.source == "rec_adopted")].set_index("year")["growth"]
    assert e.rate("home_value", 2028) == pytest.approx(rec[2028])
    target = paths[(paths.variable == "median_price_single_family")].set_index("year")["growth"]
    assert e.rate("home_value", 2036) == pytest.approx(target[2036])        # fully eased by 2036
    assert min(rec[2032], target[2033]) <= e.rate("home_value", 2033) <= max(rec[2032], target[2033])


def test_scenarios_and_overrides():
    assert Economy("stall").rate("home_value", 2028) == 0.0
    assert Economy("stall").rate("home_value", 2031) == Economy("central").rate("home_value", 2031)
    assert Economy("low").index("home_value", 2026, 2032) < Economy("central").index("home_value", 2026, 2032) \
        < Economy("high").index("home_value", 2026, 2032)
    shifted = Economy("central", overrides={"home_value": {"shift": -0.01}})
    assert shifted.rate("home_value", 2030) == pytest.approx(Economy("central").rate("home_value", 2030) - 0.01)
    with pytest.raises(ValueError):
        Economy("nope")
    with pytest.raises(ValueError):
        Economy("central", overrides={"home_value": {"multiply": 2}})


def test_grow_values_and_income():
    e = Economy("central")
    h = pd.DataFrame({"valp_market_cal": [100.0], "valp_jv_cal": [85.0], "wagp_aged": [50.0],
                      "ssp_aged": [20.0], "hincp_aged": [70.0]})
    g = e.grow(h, 2026, 2028)
    assert g.valp_market_cal[0] == pytest.approx(100 * e.index("home_value", 2026, 2028))
    assert g.ssp_aged[0] == pytest.approx(20 * e.index("cpi", 2026, 2028))
    assert g.hincp_aged[0] == pytest.approx(g.wagp_aged[0] + g.ssp_aged[0])
