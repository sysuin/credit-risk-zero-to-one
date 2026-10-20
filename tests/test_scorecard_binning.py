"""Tests for ballast.scorecard.binning: fine and coarse classes."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ballast.scorecard import binning
from ballast.scorecard.binning import Bins


@pytest.fixture(scope="module")
def toy():
    """A score whose bad rate falls as it rises, with noise and gaps."""
    rng = np.random.default_rng(7)
    n = 20_000
    x = pd.Series(rng.integers(300, 851, n).astype(float))
    p = 1 / (1 + np.exp((x - 520) / 40))
    bad = pd.Series((rng.random(n) < p).astype(int))
    x[rng.random(n) < 0.04] = np.nan          # no file
    return x, bad


def test_fine_classes_cut_at_quantiles(toy):
    x, bad = toy
    fine = binning.fine_classes("score", x, bad, missing="no file")
    assert len(fine.edges) == binning.MAX_FINE - 1
    assert fine.labels[-1] == "no file"
    assert fine.integer
    share = binning.counts(fine, x, bad)["n"][:-1] / x.notna().sum()
    assert share.between(0.03, 0.07).all()


def test_one_fine_class_per_value_when_few():
    x = pd.Series([0, 1, 1, 2, 3, 3, 3, 9], dtype=float)
    fine = binning.fine_classes("n", x)
    assert fine.labels == ["<1", "1-1", "2-2", "3-8", "9+"]
    assert fine.missing is None


def test_rounded_edges():
    x = pd.Series(np.linspace(300, 850, 1000))
    fine = binning.fine_classes("s", x, decimals=-1)
    assert all(e % 10 == 0 for e in fine.edges)


def test_missing_values_get_their_own_bin(toy):
    x, bad = toy
    fine = binning.fine_classes("score", x, bad, missing="no file")
    idx = fine.index(x)
    assert (idx[x.isna().to_numpy()] == len(fine.labels) - 1).all()
    assert (idx[x.notna().to_numpy()] < len(fine.labels) - 1).all()


def test_unlabelled_missing_is_called_missing():
    x = pd.Series([1.0, 2.0, np.nan])
    assert binning.fine_classes("v", x).missing == "missing"


def test_coarse_classes_are_monotone_and_big_enough(toy):
    x, bad = toy
    fine = binning.fine_classes("score", x, bad, missing="no file")
    coarse = binning.coarse_classes(fine, x, bad, trend="decreasing")
    assert binning.is_monotone(coarse, x, bad)
    assert binning.turns(coarse, x, bad) == 0
    c = binning.counts(coarse, x, bad)
    ordinary = c.iloc[:-1]
    assert (ordinary["n"] / ordinary["n"].sum() >= binning.MIN_SHARE).all()
    assert len(ordinary) <= binning.MAX_BINS
    assert c["bin"].iloc[-1] == "no file"      # never merged away
    rate = ordinary["bads"] / ordinary["n"]
    assert rate.is_monotonic_decreasing


def test_coarse_edges_are_a_subset_of_fine(toy):
    x, bad = toy
    fine = binning.fine_classes("score", x, bad)
    coarse = binning.coarse_classes(fine, x, bad)
    assert set(coarse.edges) <= set(fine.edges)


def test_auto_trend_finds_the_direction(toy):
    x, bad = toy
    c = binning.counts(binning.fine_classes("s", x, bad), x, bad)
    assert binning.trend_of(c["n"].to_numpy()[:-1],
                            c["bads"].to_numpy()[:-1]) == "decreasing"


def test_a_wrong_way_trend_collapses_the_bins(toy):
    x, bad = toy
    fine = binning.fine_classes("score", x, bad)
    coarse = binning.coarse_classes(fine, x, bad, trend="increasing")
    assert len(coarse.edges) == 0


def test_no_difference_means_one_bin():
    rng = np.random.default_rng(2)
    x = pd.Series(rng.normal(size=5000))
    bad = pd.Series((rng.random(5000) < 0.05).astype(int))
    fine = binning.fine_classes("noise", x, bad)
    coarse = binning.coarse_classes(fine, x, bad)
    assert len(coarse.labels) <= 2


def test_p_value():
    assert binning.p_value(1000, 50, 1000, 50) == pytest.approx(1.0)
    assert binning.p_value(1000, 20, 1000, 80) < 0.001


def test_categorical_bins_by_bad_rate():
    x = pd.Series(list("aaaabbbbcccc") * 100)
    bad = pd.Series([1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0] * 100)
    fine = binning.fine_classes("cat", x, bad)
    assert fine.kind == "categorical"
    assert fine.labels == ["c", "a", "b"]
    coarse = binning.coarse_classes(fine, x, bad)
    assert coarse.assign(pd.Series(["b"])).iloc[0] == coarse.labels[-1]


def test_unseen_category_raises():
    fine = Bins("cat", "categorical", groups=[["a"], ["b"]])
    with pytest.raises(ValueError, match="never saw"):
        fine.index(pd.Series(["a", "z"]))


def test_missing_without_a_bin_raises():
    b = Bins("v", "numeric", edges=[1.0])
    with pytest.raises(ValueError, match="no bin"):
        b.index(pd.Series([0.5, np.nan]))


def test_labels_and_assign():
    b = Bins("age", "numeric", edges=[25, 35, 50], missing="unknown",
             integer=True)
    assert b.labels == ["<25", "25-34", "35-49", "50+", "unknown"]
    got = b.assign(pd.Series([18, 25, 34, 35, 80, np.nan]))
    assert list(got.astype(str)) == ["<25", "25-34", "25-34", "35-49",
                                     "50+", "unknown"]
    f = Bins("u", "numeric", edges=[0.15, 0.4])
    assert f.labels == ["<0.15", "0.15-0.4", "0.4+"]


def test_round_trip():
    b = Bins("x", "numeric", edges=[1.0, 2.0], missing="no file",
             integer=False, woe={"<1": 0.5, "1-2": 0.0, "2+": -0.5,
                                 "no file": -0.2})
    assert Bins.from_dict(b.to_dict()) == b


def test_bin_all_uses_the_spec(toy):
    x, bad = toy
    frame = pd.DataFrame({"score": x, "half": (x > 575).astype(float)})
    spec = {"score": {"missing": "no file", "trend": "decreasing",
                      "decimals": -1},
            "half": {"kind": "numeric"}}
    out = binning.bin_all(frame, bad, spec)
    assert set(out) == {"score", "half"}
    assert out["score"].missing == "no file"
    assert all(e % 10 == 0 for e in out["score"].edges)
