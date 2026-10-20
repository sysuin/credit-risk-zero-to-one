"""Tests for ballast.models.reasons: points that add up, one reason
for no file, and the scorecard's shortfall reasons."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ballast.models import gbm, reasons
from ballast.scorecard import points
from ballast.scorecard.binning import Bins

from test_gbm import FEATURES, MONO, make


@pytest.fixture(scope="module")
def frame():
    return make(seed=5)


@pytest.fixture(scope="module")
def fitted(frame):
    return gbm.fit(frame, features=FEATURES, monotone=MONO)


def test_points_add_up_to_the_score(fitted, frame):
    pts = reasons.in_points(fitted, frame)
    assert np.allclose(pts.sum(axis=1), fitted.score(frame))


def test_no_file_is_one_reason(fitted, frame):
    pts = reasons.in_points(fitted, frame)
    g = reasons.grouped(pts, frame)
    nofile = frame["bureau_score"].isna()
    bureau = ["bureau_score", "enquiries_6m"]
    assert np.allclose(g.loc[nofile, reasons.NO_FILE],
                       pts.loc[nofile, bureau].sum(axis=1))
    assert (g.loc[nofile, bureau] == 0).all().all()
    assert (g.loc[~nofile, reasons.NO_FILE] == 0).all()
    # Nothing is lost: the grouped points still add up.
    assert np.allclose(g.sum(axis=1) + pts["base"],
                       fitted.score(frame))


def test_reason_codes_are_adverse_and_ordered(fitted, frame):
    worst = frame.loc[fitted.score(frame).idxmin()]
    r = reasons.reason_codes(fitted, worst, k=3)
    assert 0 < len(r) <= 3
    assert (r["points"] < 0).all()
    assert r["points"].is_monotonic_increasing


def test_scorecard_reasons_measure_shortfall_from_best_bin():
    b = Bins("enquiries_6m", "numeric", edges=[1, 3], integer=True,
             woe={"<1": 0.5, "1-2": 0.1, "3+": -1.0})
    f = Bins("bureau_file", "categorical",
             groups=[["file"], ["no file"]],
             woe={"file": 0.02, "no file": -0.5})
    table = pd.DataFrame([
        {"characteristic": "enquiries_6m", "bin": "<1", "points": 40},
        {"characteristic": "enquiries_6m", "bin": "1-2", "points": 30},
        {"characteristic": "enquiries_6m", "bin": "3+", "points": 0},
        {"characteristic": "bureau_file", "bin": "file", "points": 11},
        {"characteristic": "bureau_file", "bin": "no file",
         "points": 0}])
    card = points.Scorecard(450, table, {"enquiries_6m": b,
                                         "bureau_file": f})
    row = pd.Series({"enquiries_6m": 4.0, "bureau_score": np.nan})
    r = reasons.scorecard_reasons(card, row)
    assert r["characteristic"].tolist() == ["enquiries_6m",
                                            "bureau_file"]
    assert r["short"].tolist() == [40, 11]
    assert r["reason"].iloc[1] == reasons.TEXT[reasons.NO_FILE][0]
