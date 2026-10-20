"""Tests for ballast.stress: paths, satellite models, the payment
shock, the overlays and LGDs, the reverse search, and a projection on
Fernhill's book at 31 December 2025."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast import ecl, loanmath, stress
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")
S0 = {"u": 5.0, "policy": 3.75, "hpi": 137.0, "car": 112.0, "gdp": 1.5}


def _path(u=6.0, policy=5.0, hpi=120.0, car=100.0, n=60):
    return pd.DataFrame({
        "month": pd.date_range("2026-01-31", periods=n, freq="ME"),
        "u": np.linspace(S0["u"], u, n), "policy": np.full(n, policy),
        "hpi": np.linspace(S0["hpi"], hpi, n),
        "car": np.linspace(S0["car"], car, n), "gdp": np.zeros(n)})


def test_annuity_matches_loanmath():
    got = stress.annuity([25_000_000], [5.5], [300])[0]
    want = loanmath.monthly_payment(25_000_000, 5.5, 300)
    assert got == pytest.approx(want, abs=1)
    assert stress.annuity([1200], [0.0], [12])[0] == pytest.approx(100)


def test_mortgage_rates_by_type():
    m = pd.DataFrame({"rate_type": ["fixed", "variable",
                                    "fixed_then_variable",
                                    "fixed_then_variable"],
                      "rate_pct": [3.0, 6.0, 2.5, 6.25],
                      "fix_end": [0, 0, 12, -6]})
    r = stress.mortgage_rates(m, 5.75, 6, 3.75)
    assert r[0] == 3.0                     # fixed: never moves
    assert r[1] == pytest.approx(8.0)      # variable: one for one
    assert r[2] == 2.5                     # still inside its fix
    assert r[3] == pytest.approx(8.25)     # reverted already: moves
    later = stress.mortgage_rates(m, 5.75, 18, 3.75)
    assert later[2] == pytest.approx(5.75 + stress.FTV_MARGIN)


def test_scaled_paths():
    p = _path()
    flat = stress.scaled(p, S0, 0.0, ("u", "hpi", "car", "policy"))
    assert np.allclose(flat.u, S0["u"])
    assert np.allclose(flat.policy, S0["policy"])
    assert np.allclose(flat.hpi, S0["hpi"])
    same = stress.scaled(p, S0, 1.0)
    assert np.allclose(same.u, p.u) and np.allclose(same.hpi, p.hpi)
    half = stress.scaled(p, S0, 0.5)
    fall = p.hpi.iloc[-1] / S0["hpi"] - 1
    assert half.hpi.iloc[-1] / S0["hpi"] - 1 == pytest.approx(fall / 2)
    assert np.allclose(half.policy, p.policy)   # not in `what`


def test_annual_averages_and_year_ends():
    a = stress.annual(_path())
    assert list(a.index) == list(stress.YEARS)
    p = _path()
    assert a.u[2026] == pytest.approx(p.u[:12].mean())
    assert a.hpi[2027] == pytest.approx(p.hpi[23])


def test_odds_multiplier():
    p = np.array([0.0, 0.02, 0.5])
    assert np.allclose(stress._odds(p, 1.0), p)
    up = stress._odds(p, 3.0)
    assert up[0] == 0 and (up[1:] > p[1:]).all() and (up < 1).all()
    o = up[1] / (1 - up[1])
    assert o == pytest.approx(3 * 0.02 / 0.98)


def test_corp_path_carries_rates_into_the_odds():
    beta = 0.3
    inp = {"rate_beta": 0.2, "start": {"policy": 4.0},
           "params": {"long_run_u": 5.0,
                      "hazards": {"sme_term": type("H", (), {
                          "default": {"u": beta}})()}}}
    u = np.array([6.0, 7.0])
    assert np.allclose(stress.corp_path(inp, u, [4.0, 4.0]), u)
    e = stress.corp_path(inp, u, [6.0, 6.0])
    # exp(beta * extra unemployment) == exp(rate_beta * rate rise)
    assert np.exp(beta * (e - u)) == pytest.approx(np.exp(0.2 * 2.0))
    alt = stress.corp_path(inp, u, [4.0, 4.0], corp_u=0.6)
    assert np.exp(beta * (alt - 5.0)) == pytest.approx(
        np.exp(0.6 * (u - 5.0)))


def test_satellite_recovers_a_planted_slope():
    rng = np.random.default_rng(2026)
    years = np.arange(2010, 2030)
    u = rng.uniform(3, 9, len(years))
    n = np.full(len(years), 20_000)
    p = 1 / (1 + np.exp(-(-5.0 + 0.3 * u)))
    d = rng.binomial(n, p)
    h = pd.DataFrame({"year": years, "product": "x", "at_risk": n,
                      "defaults": d, "rate": d / n, "u": u})
    f = stress.fit_satellite(h, "x")
    assert f["params"]["u"] == pytest.approx(0.3, abs=0.03)
    rate, lo, hi = stress.satellite_rate(f, {"u": 8.0})
    assert lo < rate < hi
    assert rate == pytest.approx(1 / (1 + np.exp(-(-5 + 2.4))), rel=0.1)


def test_reverse_finds_the_crossing(monkeypatch):
    def fake(inp, path, name="", **kw):
        k = path.u.max() - S0["u"]           # the multiple, by design
        return {"trough_sa": 0.16 - 0.1 * k}
    monkeypatch.setattr(stress, "project", fake)
    p = _path(u=S0["u"] + 1.0)
    r = stress.reverse({"start": S0}, p, target=0.08, lo=0.0, hi=2.0)
    assert r["k"] == pytest.approx(0.8, abs=1e-3)
    assert len(r["steps"]) <= 5
    with pytest.raises(ValueError):
        stress.reverse({"start": S0}, p, target=0.5, lo=0.0, hi=1.0)


def test_module_never_reads_the_truth():
    src = Path(stress.__file__).read_text()
    assert "truth=" not in src and "TRUTH" not in src


@pytest.fixture(scope="module")
def inp():
    return stress.inputs(fernhill.connect())


@needs_book
def test_scenarios_on_the_book():
    con = fernhill.connect()
    p = stress.paths(con)
    assert set(stress.SCENARIOS) <= set(p)
    assert all(len(x) == 60 for x in p.values())
    assert p["stress_2026"].u.max() == pytest.approx(9.1)
    h = stress.historical(con, "2020-01-31", 24)
    assert len(h) == 60 and (h.policy >= 0).all()
    assert h.u.iloc[30] == h.u.iloc[59]           # held after 24


@needs_book
def test_year_zero_is_the_booked_provision(inp):
    booked = ecl.load().ecl.sum()
    assert inp["prov0"] == pytest.approx(booked, abs=1)
    s0 = inp["start"]
    lgd = inp["params"]["lgd"]
    assert stress.mortgage_lgd(inp, s0["hpi"]) == pytest.approx(
        lgd.loc["mortgage", "lgd"])
    assert stress.car_lgd(inp, s0["car"]) == pytest.approx(
        lgd.loc["auto", "lgd"])
    assert stress.cure_lgd(inp, "card", s0["u"]) == pytest.approx(
        lgd.loc["card", "lgd"])
    assert stress.mortgage_lgd(inp, s0["hpi"] * 0.7) > 2 * lgd.loc[
        "mortgage", "lgd"]
    ids = inp["book"].account_id
    assert np.allclose(stress.overlay(inp, ids, s0["policy"], 0), 1.0)


@needs_book
def test_payment_shock_and_satellites_on_the_book(inp):
    assert inp["shock_beta"] > 0               # bigger payments hurt
    assert 0 < inp["rate_beta"] < 1
    assert set(inp["pass"]) == {"card", "sme_overdraft", "sme_term"}


@needs_book
def test_a_projection_adds_up(inp):
    con = fernhill.connect()
    base = stress.project(inp, stress.paths(con)["base"], "base")
    y = base["years"]
    prev = inp["prov0"]
    cet1 = inp["bank"]["cet1"]
    for r in y.itertuples():
        assert r.charge == pytest.approx(r.loss + r.provision - prev)
        cet1 += r.nii - r.cost - r.charge
        assert r.cet1 == pytest.approx(cet1)
        prev = r.provision
    pr = base["products"]
    assert pr.loss.sum() == pytest.approx(y.loss.sum())
    assert (pr.rate.between(0, 1)).all()
    assert base["trough_sa"] == pytest.approx(y.cet1_sa.min())
