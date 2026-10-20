"""Tests for ballast.commercial.rating: the master scale, the review
sample, the penalised rating model, the analysts' moves and the
override record."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast.commercial import rating as rt
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def test_master_scale_round_trip():
    for g in rt.GRADES:
        assert rt.grade_of(rt.pd_of(g)) == g
    assert rt.pd_of(rt.DEFAULT) == 1.0
    assert list(rt.grade_of([0.0, 0.5, 1.0])) == [1, 10, 10]


def test_band_edges_are_geometric_midpoints():
    e = rt.band_edges()
    assert len(e) == 9
    assert e[0] == pytest.approx((0.0003 * 0.0007) ** 0.5)
    assert np.all(np.diff(e) > 0)
    # just either side of an edge falls in neighbouring grades
    assert rt.grade_of(e[3] * 0.999) == 4
    assert rt.grade_of(e[3] * 1.001) == 5


def toy_accounts() -> pd.DataFrame:
    return pd.DataFrame({
        "total_debt": [400_00, 100_00, 300_00],
        "ebitda": [100_00, 100_00, -5_00],
        "interest": [20_00, 0, 25_00],
        "equity": [50_00, 80_00, -10_00],
        "total_assets": [100_00, 100_00, 100_00],
        "revenue": [1_000_000_00, 10_000_000_00, 500_000_00]})


def test_features_and_their_limits():
    F = rt.features(toy_accounts())
    assert list(F.columns) == rt.FEATURES
    assert F.ln_leverage[0] == pytest.approx(np.log(4.0))
    assert F.ln_cover[0] == pytest.approx(np.log(5.0))
    # no interest: cover at the top of its range
    assert F.ln_cover[1] == pytest.approx(np.log(rt.COVER_RANGE[1]))
    # a loss: leverage at its worst, cover at its worst
    assert F.ln_leverage[2] == pytest.approx(
        np.log(rt.LEVERAGE_RANGE[1]))
    assert F.ln_cover[2] == pytest.approx(np.log(rt.COVER_RANGE[0]))
    assert F["size"][1] == pytest.approx(7.0)
    assert F.equity_ratio[2] == pytest.approx(-0.10)


def simulated(n=4000, seed=7):
    rng = np.random.default_rng(seed)
    F = pd.DataFrame({"a": rng.normal(0, 1, n),
                      "b": rng.normal(0, 1, n)})
    lo = -4 + 1.2 * F.a - 0.6 * F.b
    y = pd.Series((rng.random(n) < 1 / (1 + np.exp(-lo))).astype(int))
    return F, y


def test_fit_recovers_coefficients_without_penalty():
    F, y = simulated()
    m = rt.fit(F, y, penalty=0)
    per_unit = np.array(m.coef) / np.array(m.scale)
    assert per_unit[0] == pytest.approx(1.2, abs=0.2)
    assert per_unit[1] == pytest.approx(-0.6, abs=0.2)
    # the intercept is free, so the average PD is the default rate
    assert m.pd(F).mean() == pytest.approx(y.mean(), abs=1e-6)


def test_penalty_shrinks_and_keeps_the_average():
    F, y = simulated()
    small, big = rt.fit(F, y, 0), rt.fit(F, y, 200)
    assert np.all(np.abs(big.coef) < np.abs(small.coef))
    assert big.pd(F).mean() == pytest.approx(y.mean(), abs=1e-6)


def test_cross_validate_scores_every_row_out_of_group():
    F, y = simulated(n=1200)
    groups = pd.Series(np.arange(len(F)) % 4)
    p = rt.cross_validate(F, y, groups, penalty=1.0)
    assert p.notna().all()
    # a row's PD does not come from the model fitted on all rows
    full = rt.fit(F, y, 1.0).pd(F)
    assert not np.allclose(p, full)


def test_recalibrate_moves_level_not_ranking():
    F, y = simulated()
    m = rt.fit(F, y, 1.0)
    r = rt.recalibrate(m, F, 0.05)
    assert r.pd(F).mean() == pytest.approx(0.05, abs=1e-6)
    assert (r.log_odds(F).rank() == m.log_odds(F).rank()).all()


def test_model_round_trip(tmp_path):
    F, y = simulated(n=800)
    m = rt.fit(F, y, 3.0)
    rt.save_model(m, tmp_path)
    back = rt.load_model(tmp_path)
    assert np.allclose(back.pd(F), m.pd(F))


def test_moves_and_stickiness():
    rv = pd.DataFrame({
        "company_id": ["A"] * 4,
        "review_date": pd.to_datetime(["2020-03-31", "2021-03-31",
                                       "2022-03-31", "2023-03-31"]),
        "grade": [5, 6, 6, 9], "model_grade": [5, 7, 8, 9]})
    m = rt.moves(rv)
    assert list(m.wanted) == [2, 2, 3]
    assert list(m.moved) == [1, 0, 3]
    assert list(m.held_found) == [False, True, False]
    s = rt.stickiness(m)
    assert s.loc[2, "reviews"] == 2 and s.loc[2, "held"] == 0.5
    assert s.loc[3, "to_model"] == 1.0


def test_override_needs_reasons():
    with pytest.raises(ValueError):
        rt.Override("X", dt.date(2026, 1, 5), 3, 5)
    with pytest.raises(ValueError):
        rt.Override("X", dt.date(2026, 1, 5), 3, 11, ["why"])
    o = rt.Override("X", dt.date(2026, 1, 5), 3, 5, ["a reason"],
                    by="me", revisit_when="audit")
    assert o.notches == 2 and o.pd == 0.006
    assert all(len(line) <= 68 for line in o.lines())
    assert rt.Override("X", dt.date(2026, 1, 5), 4, 4).notches == 0


@needs_book
def test_reviews_on_the_book():
    con = fernhill.connect()
    rv = rt.reviews(con)
    dev = rv[rv.window_complete]
    assert len(dev) == 1829 and dev.default_12m.sum() == 35
    assert rv.grade.between(1, 10).all()
    # the held flag Fernhill recorded is the hold the moves find
    m = rt.moves(rv)
    assert (m.held == m.held_found).all()
    # analysts never moved a grade by exactly two notches
    assert not (m.moved.abs() == 2).any()
    want = m[m.wanted != 0]
    assert 0.2 < want.held_found.mean() < 0.35
