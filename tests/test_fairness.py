"""Tests for ballast.fairness: rates and ratios, calibration within
groups, proxies, and reasons measured against the cut-off."""
from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ballast import fairness
from ballast.scorecard import points
from ballast.scorecard.binning import Bins


def test_rates_and_adverse_impact_ratio():
    group = ["F"] * 10 + ["M"] * 10
    flag = [1] * 6 + [0] * 4 + [1] * 8 + [0] * 2
    t = fairness.rates(flag, group)
    assert t.loc["F", "n"] == 10 and t.loc["F", "yes"] == 6
    assert t.loc["M", "rate"] == pytest.approx(0.8)
    assert fairness.adverse_impact_ratio(flag, group, "F", "M") == \
        pytest.approx(0.75)


def test_air_interval_contains_the_ratio():
    rng = np.random.default_rng(1)
    g = np.where(rng.random(4000) < 0.5, "F", "M")
    y = rng.random(4000) < np.where(g == "F", 0.45, 0.50)
    air = fairness.adverse_impact_ratio(y, g, "F", "M")
    lo, hi = fairness.air_interval(y, g, "F", "M",
                                   np.random.default_rng(2), n=300)
    assert lo < air < hi
    again = fairness.air_interval(y, g, "F", "M",
                                  np.random.default_rng(2), n=300)
    assert (lo, hi) == again


def test_age_bands():
    b = fairness.age_band(pd.Series([18, 24, 25, 49, 50, 64, 65, 79]))
    assert list(b.astype(str)) == ["18-24", "18-24", "25-34", "35-49",
                                   "50-64", "50-64", "65+", "65+"]
    assert list(b.cat.categories) == fairness.AGE_LABELS


def _scored(n=20000, seed=4, tilt=0.0):
    """Loans with a calibrated promise; `tilt` makes group F riskier
    than promised by that much on the log odds."""
    rng = np.random.default_rng(seed)
    lo = rng.normal(-3.3, 0.8, n)
    g = np.where(rng.random(n) < 0.5, "F", "M")
    p = 1 / (1 + np.exp(-lo))
    true = 1 / (1 + np.exp(-(lo + tilt * (g == "F"))))
    bad = (rng.random(n) < true).astype(int)
    return p, bad, g


def test_group_effect_finds_a_tilt_and_not_its_absence():
    p, bad, g = _scored(tilt=0.0)
    fair = fairness.group_effect(p, bad, g == "F")
    assert abs(fair["coef"]) < 2.5 * fair["se"]
    p, bad, g = _scored(tilt=0.6)
    tilted = fairness.group_effect(p, bad, g == "F")
    assert tilted["coef"] > 0.3 and tilted["p"] < 0.001


def test_calibration_table():
    p, bad, g = _scored(n=5000)
    band = np.where(p < 0.04, "low", "high")
    t = fairness.calibration(p, bad, g, band)
    assert set(t.index.get_level_values(1)) == {"F", "M"}
    assert t["n"].sum() == 5000 and t["bads"].sum() == bad.sum()


def test_separation():
    rng = np.random.default_rng(3)
    f = (rng.random(5000) < 0.5).astype(int)
    noise = rng.normal(0, 1, 5000)
    assert fairness.separation(noise, f) < 0.53
    proxy = noise + 1.5 * f
    assert fairness.separation(proxy, f) > 0.8
    # Folded: the same whichever way round the proxy runs.
    assert fairness.separation(-proxy, f) == pytest.approx(
        fairness.separation(proxy, f))
    cat = pd.Series(np.where(f == 1, "a", "b")).astype("category")
    assert fairness.separation(cat, f) == pytest.approx(1.0)
    with_na = pd.Series(proxy).astype(object)
    with_na[:100] = None
    assert fairness.separation(pd.to_numeric(with_na), f) > 0.8


def _card():
    """A two-line scorecard: a wide line and a narrow one."""
    wide = Bins("wide", "numeric", edges=[1.0, 2.0, 3.0])
    narrow = Bins("narrow", "numeric", edges=[1.0])
    assert wide.labels == ["<1", "1-2", "2-3", "3+"]
    table = pd.DataFrame([
        ("wide", "<1", 0), ("wide", "1-2", 20), ("wide", "2-3", 30),
        ("wide", "3+", 40), ("narrow", "<1", 0), ("narrow", "1+", 10)],
        columns=["characteristic", "bin", "points"])
    return points.Scorecard(500, table, {"wide": wide, "narrow": narrow})


def test_reasons_against_the_cut_off_differ_from_best_bin():
    card = _card()
    # Applicants at the cut-off (530-533) mostly have the wide line's
    # second bin and the narrow line's top bin.
    chars = pd.DataFrame({"wide": [1.5, 1.5, 1.5, 0.5, 3.5],
                          "narrow": [1.5, 1.5, 1.5, 0.5, 0.5],
                          "bureau_score": [600.0] * 5})
    score = card.score(chars)
    assert list(score) == [530, 530, 530, 500, 540]
    ref = fairness.cutoff_reference(card, chars, cutoff=530)
    assert ref["wide"] == 20 and ref["narrow"] == 10
    g = fairness.gaps(card, chars, ref)
    # Each row's gaps add up to the reference score less its own.
    assert np.allclose(g.sum(axis=1), (500 + ref.sum()) - score)
    r = fairness.cutoff_reasons(card, chars, ref)
    # The applicant at 500: 20 short on the wide line, 10 on the narrow.
    assert r.iloc[3] == ("wide", "narrow")
    # One who beats the reference on the wide line is told only the
    # narrow one, though the wide line is not at its best bin either.
    chars2 = pd.DataFrame({"wide": [2.5], "narrow": [0.5],
                           "bureau_score": [600.0]})
    assert fairness.cutoff_reasons(card, chars2, ref).iloc[0] == (
        "narrow",)


def test_no_applicant_at_the_cut_off_is_an_error():
    card = _card()
    chars = pd.DataFrame({"wide": [0.5], "narrow": [0.5],
                          "bureau_score": [600.0]})
    with pytest.raises(ValueError):
        fairness.cutoff_reference(card, chars, cutoff=530)


def test_only_fairness_reads_the_monitoring_table():
    root = Path(fairness.__file__).parent
    readers = sorted(str(p.relative_to(root)) for p in root.rglob("*.py")
                     if "applicant_monitoring" in p.read_text())
    assert readers == ["fairness.py"]
    assert "truth" not in inspect.getsource(fairness)
