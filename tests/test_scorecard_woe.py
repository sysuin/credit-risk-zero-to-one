"""Tests for ballast.scorecard.woe: weight of evidence and IV."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from ballast.scorecard import woe
from ballast.scorecard.binning import Bins


@pytest.fixture
def hand():
    """Two bins worked by hand: 900 goods/100 bads overall."""
    x = pd.Series([0.0] * 500 + [1.0] * 500)
    bad = pd.Series([1] * 80 + [0] * 420 + [1] * 20 + [0] * 480)
    return Bins("flag", "numeric", edges=[1.0], integer=True), x, bad


def test_woe_by_hand(hand):
    bins, x, bad = hand
    t = woe.woe_table(bins, x, bad)
    assert list(t["goods"]) == [420, 480]
    assert list(t["bads"]) == [80, 20]
    w0 = math.log((420 / 900) / (80 / 100))
    w1 = math.log((480 / 900) / (20 / 100))
    assert t["woe"].tolist() == pytest.approx([w0, w1])
    iv = (420 / 900 - 0.8) * w0 + (480 / 900 - 0.2) * w1
    assert woe.information_value(bins, x, bad) == pytest.approx(iv)


def test_woe_is_log_odds_against_the_average(hand):
    bins, x, bad = hand
    t = woe.woe_table(bins, x, bad)
    odds = t["goods"] / t["bads"]
    assert t["woe"].tolist() == pytest.approx(
        np.log(odds / (900 / 100)).tolist())


def test_a_bin_with_no_bads_is_finite():
    x = pd.Series([0.0] * 50 + [1.0] * 50)
    bad = pd.Series([1] * 10 + [0] * 40 + [0] * 50)
    t = woe.woe_table(Bins("f", "numeric", edges=[1.0]), x, bad)
    assert np.isfinite(t["woe"]).all()
    assert t.loc[1, "pct_bad"] == pytest.approx(0.5 / 10)


def test_an_empty_bin_is_neutral():
    b = Bins("f", "numeric", edges=[1.0], missing="no file")
    t = woe.woe_table(b, pd.Series([0.0, 0.0, 2.0, 2.0]),
                      pd.Series([1, 0, 0, 0]))
    assert t.loc[2, "n"] == 0 and t.loc[2, "woe"] == 0.0


def test_fit_transform_encode(hand):
    bins, x, bad = hand
    woe.fit(bins, x, bad)
    coded = woe.encode(pd.DataFrame({"flag": x}), {"flag": bins})
    t = woe.woe_table(bins, x, bad)
    assert coded["flag"].iloc[0] == pytest.approx(t["woe"][0])
    assert coded["flag"].iloc[-1] == pytest.approx(t["woe"][1])


def test_transform_needs_fit():
    with pytest.raises(ValueError, match="fit"):
        woe.transform(Bins("f", "numeric"), pd.Series([1.0]))


def test_save_and_load(tmp_path, hand):
    bins, x, bad = hand
    woe.fit(bins, x, bad)
    path = woe.save_binset({"flag": bins}, tmp_path / "bins.json",
                           iv={"flag": 0.5})
    back = woe.load_binset(path)
    assert back["flag"].edges == bins.edges
    assert back["flag"].woe == pytest.approx(bins.woe)
    assert woe.transform(back["flag"], x).tolist() == pytest.approx(
        woe.transform(bins, x).tolist())


def test_fit_binset():
    rng = np.random.default_rng(3)
    x = pd.Series(rng.integers(0, 100, 4000).astype(float))
    bad = pd.Series((rng.random(4000) < 0.02 + x / 1000).astype(int))
    frame = pd.DataFrame({"x": x})
    binset, iv = woe.fit_binset(frame, bad, {"x": {"trend": "increasing"}})
    assert binset["x"].woe and iv["x"] > 0
    assert iv["x"] == pytest.approx(
        woe.information_value(binset["x"], x, bad))
