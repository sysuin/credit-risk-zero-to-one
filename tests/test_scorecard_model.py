"""Tests for ballast.scorecard.model: the fit, the sign rule, the
no-file design and stability."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ballast.scorecard import model, woe
from ballast.scorecard.binning import Bins


def _logistic(lo):
    return 1 / (1 + np.exp(-lo))


@pytest.fixture
def known():
    """Two WoE-like inputs and a good flag drawn from a known model:
    log odds good = 3 + 0.8 a + 0.5 b."""
    rng = np.random.default_rng(1)
    n = 40_000
    a = rng.normal(0, 1, n)
    b = rng.normal(0, 1, n)
    good = (rng.random(n) < _logistic(3 + 0.8 * a + 0.5 * b))
    X = pd.DataFrame({"a": a, "b": b})
    return X, pd.Series(good.astype(int))


def test_fit_recovers_known_coefficients(known):
    X, good = known
    r = model.fit(X, good, ["a", "b"])
    assert r.params["const"] == pytest.approx(3, abs=0.1)
    assert r.params["a"] == pytest.approx(0.8, abs=0.08)
    assert r.params["b"] == pytest.approx(0.5, abs=0.08)
    assert model.wrong_signs(r) == []


def test_one_woe_characteristic_has_coefficient_one():
    """WoE is already the log of the odds ratio, so alone it enters
    with a coefficient of exactly 1 and the constant is ln(odds)."""
    x = pd.Series([0.0] * 500 + [1.0] * 500)
    bad = pd.Series([1] * 80 + [0] * 420 + [1] * 20 + [0] * 480)
    b = Bins("flag", "numeric", edges=[1.0], integer=True)
    woe.fit(b, x, bad)
    X = woe.encode(pd.DataFrame({"flag": x}), {"flag": b})
    r = model.fit(X, model.target(pd.DataFrame({"bad": bad})), ["flag"])
    assert r.params["flag"] == pytest.approx(1.0, abs=1e-6)
    assert r.params["const"] == pytest.approx(np.log(900 / 100),
                                              abs=1e-6)


def test_target_is_good():
    t = model.target(pd.DataFrame({"bad": [0, 1, 0]}))
    assert t.tolist() == [1, 0, 1]


@pytest.fixture
def overlap():
    """`b` adds nothing beyond `a` except a shared spike that `a`
    already carries: fitted together, `b` takes the wrong sign."""
    rng = np.random.default_rng(2)
    n = 30_000
    spike = rng.random(n) < 0.05
    a = np.where(spike, -1.0, rng.normal(0.1, 1, n))
    b = np.where(spike, -1.0, rng.normal(0.1, 1, n))
    lo = 3 + 0.9 * a + 0.0 * b + np.where(spike, 1.5, 0)
    good = (rng.random(n) < _logistic(lo)).astype(int)
    return pd.DataFrame({"a": a, "b": b}), pd.Series(good)


def test_select_refuses_a_wrong_sign(overlap):
    X, good = overlap
    both = model.fit(X, good, ["a", "b"])
    assert "b" in model.wrong_signs(both)
    chosen, steps = model.select(X, good, ["a", "b"], alpha=0.5)
    assert chosen == ["a"]
    assert steps[-1].added is None and "b" in steps[-1].wrong_sign


def test_select_stops_at_alpha(known):
    X, good = known
    rng = np.random.default_rng(3)
    X = X.assign(noise=rng.normal(0, 1, len(X)))
    chosen, _ = model.select(X, good, ["a", "b", "noise"], alpha=0.001)
    assert chosen == ["a", "b"]


def test_select_keeps_forced(known):
    X, good = known
    chosen, steps = model.select(X, good, ["a"], force=["b"])
    assert chosen == ["b", "a"]
    assert steps[0].added == "a"


def _binset():
    score = Bins("bureau_score", "numeric", edges=[650.0],
                 missing="no file", integer=True,
                 woe={"<650": -0.5, "650+": 0.4, "no file": -0.6})
    inc = Bins("income", "numeric", edges=[30000.0], integer=True,
               woe={"<30,000": -0.2, "30,000+": 0.2})
    return {"bureau_score": score, "income": inc}


def test_separate_no_file_is_neutral_and_adds_a_flag():
    frame = pd.DataFrame({
        "bureau_score": [600, 700, np.nan, np.nan, 700, 600],
        "income": [20000, 40000, 50000, 10000, 35000, 25000],
        "bad": [1, 0, 1, 0, 0, 0]})
    original = _binset()
    design = model.separate_no_file(original, frame, frame["bad"])
    assert design["bureau_score"].woe["no file"] == 0.0
    assert original["bureau_score"].woe["no file"] == -0.6
    assert design["income"].woe == original["income"].woe
    flag = design[model.FILE_FLAG]
    assert flag.labels == ["file", "no file"]
    # 4 goods and 2 bads in all; file holds 3 goods and 1 bad.
    assert flag.woe["file"] == pytest.approx(np.log((3 / 4) / (1 / 2)))
    assert flag.woe["no file"] == pytest.approx(np.log((1 / 4) / (1 / 2)))
    coded = woe.encode(model.with_file_flag(frame), design)
    assert coded.loc[2, "bureau_score"] == 0.0
    assert coded.loc[2, model.FILE_FLAG] == flag.woe["no file"]


def test_stability_has_every_split(known):
    X, good = known
    split = pd.Series(np.where(np.arange(len(X)) % 3 == 0, "holdout",
                               np.where(np.arange(len(X)) % 3 == 1,
                                        "out_of_time", "train")))
    t = model.stability(X, good, split, ["a", "b"])
    assert list(t.index) == ["const", "a", "b"]
    assert {"train_coef", "holdout_z", "out_of_time_z"} <= set(t.columns)
    # Same model in every third: the estimates agree within noise.
    assert (t["holdout_z"].abs() < 4).all()


def test_saved_mark2_has_only_positive_signs():
    path = model.MARK2 / "model.json"
    if not path.exists():
        pytest.skip("Mark II not saved yet (code/08/14_save_mark2.py)")
    d = model.load_model()
    assert d["characteristics"] == model.CHARACTERISTICS
    assert all(v > 0 for v in d["coef"].values())
