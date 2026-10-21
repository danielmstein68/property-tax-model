from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ptm.economy import Economy
from ptm.tx.project import PATHS, SPEC, pop_factors

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"
HAVE = (PROC / "tx_baseline_2026.parquet").exists() and (PROC / "tx_baseline_2026_units.parquet").exists()


def test_tx_economy_paths():
    e = Economy("central", assumptions_path=SPEC, paths_path=PATHS)
    assert e.rate("home_value", 2027) == pytest.approx(0.015)
    assert e.rate("wage", 2027) == pytest.approx(0.048, abs=0.001)        # Comptroller CRE 2026-27
    assert e.rate("wage", 2032) == pytest.approx(0.036)                   # eased to the long-run rate
    d = Economy("downturn", assumptions_path=SPEC, paths_path=PATHS)
    assert d.rate("home_value", 2027) == pytest.approx(-0.05)


def test_pop_factors_grow_faster_at_65_plus():
    f = pop_factors(range(2026, 2037))
    assert f.loc[2026].tolist() == pytest.approx([1.0, 1.0])
    assert f.loc[2036, "65_plus"] > f.loc[2036, "18_64"] > 1.0


@pytest.fixture(scope="module")
def run():
    if not HAVE:
        pytest.skip("needs the Texas baseline (python -m ptm.tx.project --rebuild)")
    from ptm.tx.project import TxProjection
    o = pd.read_parquet(PROC / "tx_baseline_2026.parquet")
    rows = pd.read_parquet(PROC / "tx_baseline_2026_units.parquet")
    return o, TxProjection(o, rows, "central", end_year=2029).run()


def test_base_year_matches_baseline(run):
    o, p = run
    t = pd.Series(p.history["tax_2026"][p.orig], index=o.index)
    assert np.allclose(t, o["tax_total"].fillna(0), atol=0.01)


def test_owners_by_age_band_follow_population(run):
    o, p = run
    f = pop_factors(range(2026, 2031))
    w, age = p.history["weight_2029"], p.history["age_2029"]
    assert w[age >= 65].sum() == pytest.approx(p.band_t0["65_plus"] * f.loc[2029, "65_plus"], rel=1e-9)
    assert w[age < 65].sum() == pytest.approx(p.band_t0["18_64"] * f.loc[2029, "18_64"], rel=1e-9)


def test_owners_turning_65_claim_and_freeze(run):
    o, p = run
    s = p.summary
    assert (s.loc[2027:, "new_over65_claims"] > 0).all()
    assert s.loc[2029, "homesteads_65_or_disabled"] > s.loc[2026, "homesteads_65_or_disabled"]
    assert 0.04 < s.loc[2027, "homestead_share_reset"] < 0.07                  # sales + deaths near the PUMS 5.6%
