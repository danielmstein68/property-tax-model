import numpy as np
import pandas as pd

from ptm import topcode
from ptm.topcode import quantile_map


def test_quantile_map_reproduces_tail_distribution():
    tail = np.arange(1, 1001) * 1000.0  # 1,000 parcels
    rng = np.random.default_rng(0)
    scores = rng.random(500)
    weights = rng.uniform(1, 3, 500)
    v = quantile_map(scores, weights, tail)
    # weighted quartiles of the result match the tail's quartiles (within 1%)
    order = np.argsort(v)
    cum = np.cumsum(weights[order]) / weights.sum()
    for q in (0.25, 0.5, 0.75):
        got = v[order][np.searchsorted(cum, q)]
        assert abs(got / np.quantile(tail, q) - 1) < 0.01


def test_quantile_map_higher_score_gets_higher_value():
    v = quantile_map(np.array([0.9, 0.1, 0.5]), np.ones(3), np.array([10.0, 20.0, 30.0]))
    assert v[1] < v[2] < v[0]
    assert v.min() >= 10 and v.max() <= 30


def _fake_roll(base_year):
    # Region "001": 40 parcels from $3.0M to $6.9M; region "003": 40 parcels from $3.5M to $7.4M;
    # 200 cheaper parcels (below any cut-off) in each county.
    rows = []
    for c, start in [("001", 3_000_000), ("003", 3_500_000)]:
        rows += [(c, "sfr", start + 100_000 * i) for i in range(40)]
        rows += [(c, "sfr", 500_000 + 1_000 * i) for i in range(200)]
    d = pd.DataFrame(rows, columns=["county_fips", "type", "value_survey"])
    d["market"] = d["value_survey"]
    d["jv"] = d["value_survey"] * 0.83
    return d


def _households():
    n = 60
    return pd.DataFrame({
        "tenure": ["owner"] * n + ["renter"],
        "county_fips": ["001"] * 30 + ["003"] * 30 + ["001"],
        "flag_topcode_valp": [True] * 40 + [False] * 20 + [False],
        "VALP": [6_471_000.0] * 40 + [400_000.0] * 20 + [np.nan],
        "TAXAMT": list(np.linspace(5_000, 42_500, 40)) + [3_000.0] * 20 + [np.nan],
        "WGTP": [2.0] * 61,
        "value_growth": [1.0] * 61,
        "jv_to_market": [0.83] * 61,
        "valp_market_aged": [6_471_000.0] * 40 + [400_000.0] * 20 + [np.nan],
        "valp_jv_aged": [6_471_000.0 * 0.83] * 40 + [332_000.0] * 20 + [np.nan],
    })


def test_impute_topcoded_values(monkeypatch):
    monkeypatch.setattr(topcode, "roll_tail_values", _fake_roll)
    h = _households()
    out, rep = topcode.impute_topcoded_values(h, 2026, min_records=10, min_tail=10)
    tc = h["flag_topcode_valp"]

    # Every top-coded value replaced, at or above the statewide cut-off, within the real tail
    assert (out.loc[tc, "valp_2024"] != 6_471_000).all()
    assert (out.loc[tc, "valp_2024"] >= rep["statewide_cutoff_2024"].iloc[0] - 1).all()
    assert out.loc[tc, "valp_2024"].max() <= 7_400_000
    # Non-top-coded rows unchanged; VALP itself untouched
    pd.testing.assert_series_equal(out.loc[~tc, "valp_2024"], h.loc[~tc, "VALP"], check_names=False)
    pd.testing.assert_series_equal(out["VALP"], h["VALP"])
    # 2026 values follow from the household's own factors
    np.testing.assert_allclose(out.loc[tc, "valp_jv_aged"], out.loc[tc, "valp_2024"] * 0.83)
    # Reported tax and imputed value move together
    assert (rep["tax_value_rank_corr"] > 0).all()


def test_impute_is_deterministic(monkeypatch):
    monkeypatch.setattr(topcode, "roll_tail_values", _fake_roll)
    a, _ = topcode.impute_topcoded_values(_households(), 2026, min_records=10, min_tail=10)
    b, _ = topcode.impute_topcoded_values(_households(), 2026, min_records=10, min_tail=10)
    pd.testing.assert_series_equal(a["valp_2024"], b["valp_2024"])
