import numpy as np
import pandas as pd
import pytest

from ptm.results import suits_index, weighted_cutoffs


def test_suits_proportional_is_zero():
    inc = np.array([10, 20, 30, 40.0]); w = np.ones(4)
    assert suits_index(inc, 0.05 * inc, w) == pytest.approx(0, abs=1e-12)


def test_suits_signs():
    inc = np.array([10, 20, 30, 40.0]); w = np.ones(4)
    assert suits_index(inc, np.full(4, 5.0), w) < 0            # flat tax: regressive
    assert suits_index(inc, inc ** 2 / 100, w) > 0             # rising share: progressive


def test_weighted_cutoffs():
    x = pd.Series(np.arange(1, 101, dtype=float)); w = pd.Series(np.ones(100))
    c = weighted_cutoffs(x, w)
    assert len(c) == 9 and c[4] == pytest.approx(50, abs=1)


def test_weighted_median():
    from ptm.results import weighted_median
    assert weighted_median([1, 2, 3], [1, 1, 1]) == 2
    assert weighted_median([1, 2, 3], [1, 1, 10]) == 3
    assert weighted_median([1, np.inf, np.inf], [1, 1, 1]) == np.inf
