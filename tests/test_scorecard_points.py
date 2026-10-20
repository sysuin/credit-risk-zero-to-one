"""Tests for ballast.scorecard.points: the scale and the table."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from ballast.scorecard import points
from ballast.scorecard.binning import Bins


def test_scale_anchors():
    assert points.odds_at(600) == pytest.approx(50)
    assert points.odds_at(620) == pytest.approx(100)
    assert points.odds_at(580) == pytest.approx(25)
    assert points.bad_rate_at(600) == pytest.approx(1 / 51)
    assert points.score_from_log_odds(math.log(50)) == pytest.approx(600)


def test_twenty_points_double_the_odds_everywhere():
    s = np.arange(400, 800, 7.0)
    assert points.odds_at(s + 20) / points.odds_at(s) == \
        pytest.approx(np.full(len(s), 2.0))


def _card():
    a = Bins("a", "numeric", edges=[10.0], integer=True,
             woe={"<10": -0.7, "10+": 0.5})
    b = Bins("b", "categorical", groups=[["x"], ["y", "z"]],
             woe={"x": 0.3, "y/z": -0.4})
    coef = {"const": 3.2, "a": 0.9, "b": 0.6}
    return coef, {"a": a, "b": b}


def test_riskiest_bin_earns_nothing():
    coef, binset = _card()
    card = points.scorecard(coef, binset)
    low = card.table.groupby("characteristic")["points"].min()
    assert (low == 0).all()
    assert card.characteristics == ["a", "b"]


def test_score_matches_the_log_odds():
    coef, binset = _card()
    card = points.scorecard(coef, binset)
    frame = pd.DataFrame({"a": [3, 12, 12, 5], "b": ["x", "z", "x", "y"]})
    exact = points.exact_score(coef, binset, frame)
    lo = coef["const"] + coef["a"] * np.array([-0.7, 0.5, 0.5, -0.7]) \
        + coef["b"] * np.array([0.3, -0.4, 0.3, -0.4])
    assert exact.to_numpy() == pytest.approx(points.score_from_log_odds(lo))
    got = card.score(frame)
    assert got.dtype.kind == "i"
    # base and two lines, each rounded: within 1.5 points.
    assert (got - exact).abs().max() <= 1.5


def test_explain_adds_up():
    coef, binset = _card()
    card = points.scorecard(coef, binset)
    row = pd.Series({"a": 12, "b": "z"})
    lines = card.explain(row)
    assert list(lines["bin"]) == ["10+", "y/z"]
    total = card.base + lines["points"].sum()
    assert total == card.score(row.to_frame().T).iloc[0]


def test_save_and_load(tmp_path):
    coef, binset = _card()
    card = points.scorecard(coef, binset)
    points.save_scorecard(card, tmp_path)
    back = points.load_scorecard(tmp_path)
    frame = pd.DataFrame({"a": [3, 12], "b": ["x", "y"]})
    assert back.base == card.base
    assert back.score(frame).tolist() == card.score(frame).tolist()
    csv = pd.read_csv(tmp_path / "points_table.csv")
    assert csv.iloc[0]["characteristic"] == "base"
