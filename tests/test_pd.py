"""Tests for ballast.parameters.pd: calibration, grading, the
12-month model, survival curves, the hazard model and the
low-default estimates."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast.config import LOANBOOK
from ballast.parameters import pd as pdm

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")
RNG = np.random.default_rng(18)


def test_platt_recovers_a_known_curve():
    s = RNG.uniform(520, 660, 40_000)
    p = 1 / (1 + np.exp(-(20.0 - 0.04 * s)))
    y = (RNG.random(len(s)) < p).astype(int)
    cal = pdm.fit_calibration(s, y, "platt")
    assert abs(cal.b + 0.04) < 0.004 and abs(cal.a - 20.0) < 2.0
    assert abs(cal.pd(s).mean() - y.mean()) < 1e-6   # mean matches


def test_isotonic_never_rises_with_score():
    s = RNG.uniform(520, 660, 5_000)
    y = (RNG.random(len(s)) < 1 / (1 + np.exp(-(20 - 0.04 * s))))
    cal = pdm.fit_calibration(s, y.astype(int), "isotonic")
    grid = np.linspace(500, 680, 200)
    assert np.all(np.diff(cal.pd(grid)) <= 1e-12)
    with pytest.raises(ValueError):
        pdm.fit_calibration(s, y, "magic")


def test_retail_grade_uses_scale_and_pools():
    g = pdm.retail_grade([0.006, 0.05, 0.3, 0.3], [0, 0, 1, 2])
    assert g.tolist() == ["5", "8", "30", "60"]


def test_ahead_averages_the_next_months():
    u = pd.Series(np.arange(1.0, 25.0),
                  index=pd.date_range("2020-01-31", periods=24,
                                      freq="ME"))
    a = pdm.ahead(u, 12)
    assert a.iloc[0] == pytest.approx(np.mean(np.arange(2.0, 14.0)))
    assert np.isnan(a.iloc[-1])


def test_pd_model_macro_moves_level_not_order():
    n = 30_000
    frame = pd.DataFrame({
        "score": RNG.uniform(520, 660, n), "mob": RNG.integers(1, 60, n),
        "missed": RNG.choice([0, 1, 2], n, p=[.95, .03, .02]),
        "u_ahead": RNG.uniform(4, 8, n), "complete": True})
    z = (12 - 0.03 * frame.score + 2.7 * (frame.missed == 1)
         + 3.9 * (frame.missed == 2) + 0.3 * frame.u_ahead)
    frame["y"] = (RNG.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    m = pdm.fit_pd_model(frame, macro=True)
    assert abs(m.params["u_ahead"] - 0.3) < 0.08
    lo, hi = m.pd(frame, u_ahead=4.0), m.pd(frame, u_ahead=8.0)
    assert (hi > lo).all()
    assert np.array_equal(np.argsort(lo.to_numpy()),
                          np.argsort(hi.to_numpy()))
    with pytest.raises(ValueError):
        pdm.fit_pd_model(frame.assign(complete=False))


def toy_durations():
    # 10 loans: 3 default (months 1, 2, 4), 4 close (1, 2, 3, 3),
    # 3 censored at month 4
    return pd.DataFrame({"t": [1, 2, 4, 1, 2, 3, 3, 4, 4, 4],
                         "event": [1, 1, 1, 2, 2, 2, 2, 0, 0, 0]})


def test_life_table_and_curves_by_hand():
    t = pdm.life_table(toy_durations(), 4)
    assert t.at_risk.tolist() == [10, 8, 6, 4]
    km = pdm.kaplan_meier(t)
    ci = pdm.cumulative_incidence(t)
    # KM: 1 - (9/10)(7/8)(6/6)(3/4)
    assert km[4] == pytest.approx(1 - 0.9 * 7 / 8 * 3 / 4)
    # CI: 1/10 + (8/10)(1/8) + 0 + (8/10)(6/8)(4/6)(1/4)
    assert ci[4] == pytest.approx(0.1 + 0.1 + 0.1)
    assert (ci <= km + 1e-12).all()


def test_hazard_model_recovers_a_constant_hazard():
    n = 4_000
    t = RNG.geometric(0.02, n)
    c = RNG.geometric(0.03, n)
    d = pd.DataFrame({"t": np.minimum(np.minimum(t, c), 48),
                      "start": pd.Timestamp("2016-01-31"),
                      "band": "all"})
    d["event"] = np.where(t <= np.minimum(c, 48), 1,
                          np.where(c <= 48, 2, 0))
    u = pd.Series(5.0, index=pd.date_range("2016-01-31", periods=60,
                                           freq="ME"))
    pm = pdm.person_months(d, u)
    pm["u"] = RNG.normal(5, 1, len(pm))      # unrelated to default
    hm = pdm.fit_hazard("toy", pm)
    h = hm.hazard(np.arange(1, 49), "all", 5.0)
    assert np.allclose(h, 0.02, atol=0.006)
    ts = hm.term_structure("all", np.full(24, 5.0))
    assert ts.cumulative_pd.is_monotonic_increasing
    assert ts.cumulative_pd.iloc[-1] == pytest.approx(
        ts.marginal_pd.sum())


def test_pluto_tasche_zero_defaults_closed_form():
    n, gamma = [100, 200, 300], 0.9
    got = pdm.pluto_tasche(n, [0, 0, 0], gamma)
    want = [1 - (1 - gamma) ** (1 / sum(n[k:])) for k in range(3)]
    assert np.allclose(got, want, rtol=1e-6)
    assert np.all(np.diff(got) > 0)          # fewer obligors, higher


def test_pluto_tasche_correlation_raises_the_bound():
    n, d = [300, 300], [0, 1]
    ind = pdm.pluto_tasche(n, d, 0.9)
    cor = pdm.pluto_tasche(n, d, 0.9, rho=0.12, years=4, sims=1500,
                           seed=1)
    assert (cor > ind).all()


def test_bayes_scale_follows_the_data_and_keeps_order():
    grades = np.arange(1, 11)
    true = 1 / (1 + np.exp(-(-9 + 0.7 * grades)))
    n = np.full(10, 20_000)
    d = RNG.binomial(n, true)
    post = pdm.bayes_scale(n, d, grades)
    assert post["mean"].is_monotonic_increasing
    assert np.allclose(post["mean"], true, rtol=0.25)
    assert (post.lower <= post["mean"]).all()
    assert (post["mean"] <= post.upper).all()


def test_band_labels():
    b = pdm.band([500, 560, 579, 600, 650], [560, 580, 600, 620])
    assert b.tolist() == ["<560", "560-579", "560-579", "600-619",
                          "620+"]


def test_module_never_reads_the_truth():
    src = Path(pdm.__file__).read_text()
    assert "truth=True" not in src and "TRUTH" not in src


@needs_book
def test_personal_loans_and_panel_on_the_book():
    con = fernhill.connect()
    loans = pdm.personal_loans(con)
    assert len(loans) == 26_688 and loans.account_id.is_unique
    assert loans.score.between(484, 652).all()
    panel = pdm.account_months(con, loans)
    assert (panel.missed <= 2).all() and (panel.mob >= 1).all()
    assert panel.groupby(["account_id", "month"]).size().max() == 1
    assert panel.loc[panel.complete, "u_ahead"].notna().all()


@needs_book
def test_durations_and_cycle_on_the_book():
    con = fernhill.connect()
    d = pdm.durations(con, "card")
    assert d.account_id.str.startswith("CC").all()   # stitched roots
    assert set(d.event) == {0, 1, 2} and (d.t >= 1).all()
    from ballast import performance as perf
    eps = perf.default_episodes(con, pdm.DEFINITION)
    r = pdm.annual_default_rates(con, eps, ["personal"], [2025])
    assert r.rate.iloc[0] == pytest.approx(0.0243, abs=5e-5)


@needs_book
def test_saved_parameters_reload():
    path = pdm.PARAMS / "pd_hazard.json"
    if not path.exists():
        pytest.skip("parameters not saved yet (code/18/17)")
    hz = pdm.load_hazards()
    assert set(hz) >= {"personal", "card", "mortgage", "sme_emergency"}
    h = hz["personal"].hazard([12], "580-599", [5.0])
    assert 0 < h[0] < 0.01
    assert pdm.load_calibration().method == "platt"
