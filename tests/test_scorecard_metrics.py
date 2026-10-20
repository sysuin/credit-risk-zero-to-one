"""Tests for ballast.scorecard.metrics: ranking and calibration."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from ballast.scorecard import metrics


@pytest.fixture
def scored():
    rng = np.random.default_rng(4)
    n = 5000
    score = rng.normal(600, 30, n).round()
    p_bad = 1 / (1 + np.exp((score - 487) / 28.85))
    bad = (rng.random(n) < p_bad).astype(int)
    return score, bad, p_bad


def test_auc_matches_sklearn_with_ties(scored):
    score, bad, _ = scored
    # sklearn scores the positive class (good) higher.
    assert metrics.auc(score, bad) == pytest.approx(
        roc_auc_score(1 - bad, score))


def test_gini_extremes():
    bad = np.array([1, 1, 0, 0, 0])
    assert metrics.gini([1, 2, 3, 4, 5], bad) == pytest.approx(1)
    assert metrics.gini([5, 4, 3, 2, 1], bad) == pytest.approx(-1)
    assert metrics.gini([7, 7, 7, 7, 7], bad) == pytest.approx(0)


def test_ks_by_hand():
    # Bads at 1 and 3; goods at 2, 4, 5. At score 1: 1/2 vs 0;
    # at 3: 2/2 vs 1/3 -> gap 2/3, the largest.
    k, at = metrics.ks([1, 2, 3, 4, 5], [1, 0, 1, 0, 0])
    assert k == pytest.approx(2 / 3)
    assert at == 3


def test_curves_run_from_zero_to_one(scored):
    score, bad, _ = scored
    roc = metrics.roc_points(score, bad)
    cap = metrics.cap_points(score, bad)
    for t, x in ((roc, "goods"), (cap, "loans")):
        assert t[x].iloc[0] == 0 and t[x].iloc[-1] == pytest.approx(1)
        assert t["bads"].iloc[-1] == pytest.approx(1)
        assert (np.diff(t["bads"]) >= 0).all()
    # Area under the ROC curve is the AUC.
    area = np.trapezoid(roc["bads"], roc["goods"])
    assert area == pytest.approx(metrics.auc(score, bad), abs=1e-9)


def test_calibration_counts(scored):
    score, bad, p_bad = scored
    t = metrics.calibration(score, bad, p_bad, [570, 600, 630])
    assert t["loans"].sum() == len(score)
    assert t["bads"].sum() == bad.sum()
    assert list(t["band"]) == ["<570", "570-599", "600-629", "630+"]
    # Simulated from p_bad: no band should be far off.
    assert (t["p_value"] > 0.001).all()


def test_hosmer_lemeshow_tells_calibrated_from_shifted(scored):
    score, bad, p_bad = scored
    _, _, p_ok = metrics.hosmer_lemeshow(p_bad, bad)
    _, _, p_off = metrics.hosmer_lemeshow(p_bad / 2, bad)
    assert p_ok > 0.01
    assert p_off < 1e-6


def test_bootstrap_is_seeded(scored):
    score, bad, _ = scored
    a = metrics.bootstrap(metrics.gini, score, bad, n=50,
                          rng=np.random.default_rng(9))
    b = metrics.bootstrap(metrics.gini, score, bad, n=50,
                          rng=np.random.default_rng(9))
    assert (a == b).all()
    lo, hi = metrics.interval(a)
    assert lo < metrics.gini(score, bad) < hi


def test_needs_goods_and_bads():
    with pytest.raises(ValueError):
        metrics.auc([1, 2, 3], [0, 0, 0])
