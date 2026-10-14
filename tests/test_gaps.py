import numpy as np

from ptm.gaps import quantile_pick


def test_quantile_pick_order_and_coverage():
    scores = np.array([0.9, 0.1, 0.5, 0.3])
    weights = np.ones(4)
    pos = quantile_pick(scores, weights, n_tail=8)
    # lower score -> lower (or equal) donor position
    assert list(np.argsort(pos, kind="stable")) == list(np.argsort(scores, kind="stable"))
    assert pos.min() >= 0 and pos.max() <= 7


def test_quantile_pick_respects_weights():
    # one heavy household takes most of the distribution: its position is near the middle
    scores = np.array([0.0, 1.0, 2.0])
    weights = np.array([1.0, 98.0, 1.0])
    pos = quantile_pick(scores, weights, n_tail=100)
    assert pos[0] == 0 and pos[2] == 99 and 45 <= pos[1] <= 55
