"""Tests for ballast.models.gbm: the fold, the constraints, the scale,
repeatability and the save and load round trip."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ballast.models import gbm
from ballast.scorecard import points

FEATURES = ["bureau_score", "enquiries_6m", "income", "channel"]
MONO = {"bureau_score": -1, "enquiries_6m": +1}


def make(n=6000, seed=3):
    """Applicants whose risk falls with the bureau score and rises with
    enquiries, with some bureau scores missing, as for no-file."""
    rng = np.random.default_rng(seed)
    bs = rng.normal(680, 60, n)
    enq = rng.poisson(1.0, n).astype(float)
    income = rng.lognormal(10.5, 0.4, n)
    channel = rng.choice(["online", "branch", "broker"], n)
    lo = -3.3 - 0.02 * (bs - 680) + 0.5 * (enq - 1)
    bad = (rng.random(n) < 1 / (1 + np.exp(-lo))).astype(int)
    bs[rng.random(n) < 0.05] = np.nan
    enq[np.isnan(bs)] = np.nan
    return pd.DataFrame({"bureau_score": bs, "enquiries_6m": enq,
                         "income": income, "channel": channel,
                         "bad": bad, "fit": rng.random(n) < 0.7})


@pytest.fixture(scope="module")
def frame():
    return make()


@pytest.fixture(scope="module")
def fitted(frame):
    return gbm.fit(frame, features=FEATURES, monotone=MONO)


def test_validation_fold_is_stratified_and_repeatable():
    bad = pd.Series([1] * 50 + [0] * 950)
    a, b = gbm.validation_fold(bad), gbm.validation_fold(bad)
    assert a.equals(b)
    assert a.sum() == 200
    assert bad[a].sum() == 10


def test_constraints_follow_the_feature_order():
    assert gbm.constraints(["income", "dti", "bureau_score"],
                           gbm.MONOTONE) == [0, 1, -1]


def test_design_keeps_missing_and_unseen_categories_missing():
    f = pd.DataFrame({"income": [1.0, None], "channel": ["online",
                                                         "carrier"]})
    x = gbm.design(f, ["income", "channel"], {"channel": ["online"]})
    assert np.isnan(x["income"].iloc[1])
    assert x["channel"].isna().tolist() == [False, True]


def test_fit_finds_the_signal_and_stops_early(fitted, frame):
    from ballast.scorecard import metrics
    test = frame[~frame["fit"]]
    assert metrics.gini(fitted.score(test), test["bad"]) > 0.4
    assert 0 < fitted.rounds < gbm.MAX_ROUNDS
    best = int(np.argmin(fitted.history)) + 1
    assert fitted.rounds == best


def test_constraints_hold_for_every_applicant(fitted, frame):
    assert gbm.wrong_way(fitted, frame, "enquiries_6m", 1) == 0
    assert gbm.wrong_way(fitted, frame, "bureau_score", 20,
                         riskier=-1) == 0
    pdp = gbm.partial_dependence(fitted, frame, "bureau_score",
                                 range(500, 860, 20))
    assert (np.diff(pdp.to_numpy()) <= 1e-12).all()


def test_fit_is_repeatable(fitted, frame):
    again = gbm.fit(frame, features=FEATURES, monotone=MONO)
    assert np.array_equal(again.raw(frame), fitted.raw(frame))


def test_score_is_on_mark_ii_scale(fitted, frame):
    raw = fitted.raw(frame)
    expect = points.score_from_log_odds(-raw)
    assert np.allclose(fitted.score(frame), expect)
    # 1 in 51 going bad is odds of 50 to 1: 600 points.
    assert points.score_from_log_odds(np.log(50)) == pytest.approx(600)


def test_contributions_add_up(fitted, frame):
    c = fitted.contributions(frame.head(50))
    assert np.allclose(c.sum(axis=1), fitted.raw(frame.head(50)))


def test_save_and_load_round_trip(fitted, frame, tmp_path):
    gbm.save(fitted, tmp_path, extra={"note": "test"})
    back = gbm.load(tmp_path)
    assert back.rounds == fitted.rounds
    assert back.monotone == fitted.monotone
    assert np.array_equal(back.raw(frame), fitted.raw(frame))


def test_size_counts_leaves_and_splits(fitted):
    sz = gbm.size(fitted)
    assert sz["trees"] == fitted.rounds
    assert sz["splits"] == sz["leaves"] - sz["trees"]
