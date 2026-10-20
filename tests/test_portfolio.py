"""Tests for ballast.portfolio: the Vasicek distribution, correlation
from default history, the simulation and the concentration measures."""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import fernhill
from ballast import capital
from ballast import portfolio as pf
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


# ------------------------------------------------------- Vasicek

def test_quantile_inverts_the_distribution():
    for p, rho in [(0.02, 0.15), (0.04, 0.10), (0.005, 0.01)]:
        for q in (0.1, 0.5, 0.99, 0.999):
            x = pf.vasicek_quantile(q, p, rho)
            assert pf.vasicek_cdf(x, p, rho) == pytest.approx(q)


def test_conditional_pd_averages_to_the_pd():
    x = np.linspace(-9, 9, 4001)
    w = norm.pdf(x) * (x[1] - x[0])
    for rho in (0.01, 0.15, 0.4):
        assert (w * pf.conditional_pd(0.03, rho, x)).sum() \
            == pytest.approx(0.03, rel=1e-6)


def test_density_integrates_to_one_and_variance_grows():
    x = np.linspace(1e-6, 1 - 1e-6, 400_001)
    f = pf.vasicek_pdf(x, 0.03, 0.10)
    assert (f * (x[1] - x[0])).sum() == pytest.approx(1, abs=1e-3)
    v = [pf.vasicek_variance(0.03, r) for r in (0.01, 0.05, 0.2)]
    assert v[0] < v[1] < v[2]
    assert pf.vasicek_variance(0.03, 0.0) == 0.0


def test_expected_shortfall_is_beyond_the_quantile():
    q = pf.vasicek_quantile(0.999, 0.02, 0.15)
    assert pf.vasicek_es(0.999, 0.02, 0.15) > q


def test_formula_matches_chapter_21_capital():
    k = capital.capital_k(0.01, 0.45, "mortgage")
    assert pf.asrf_capital([1.0], [0.45], [0.01], 0.15) \
        == pytest.approx(float(k))


# ------------------------------------------------- estimation

def history(rho, p=0.03, n=20_000, years=300, seed=1):
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(years)
    at = np.full(years, n)
    d = rng.binomial(at, pf.conditional_pd(p, rho, z))
    return d, at, z


def test_moments_recover_a_known_correlation():
    d, n, _ = history(0.05)
    assert pf.mom_rho(d / n, n) == pytest.approx(0.05, abs=0.012)


def test_likelihood_recovers_it_and_its_interval_covers_it():
    d, n, _ = history(0.05, years=60, seed=2)
    fit = pf.fit_rho(d, n)
    assert fit["rho"] == pytest.approx(0.05, abs=0.015)
    assert fit["lo"] < 0.05 < fit["hi"]
    assert fit["p"] == pytest.approx(0.03, abs=0.004)


def test_independent_defaults_give_a_correlation_near_zero():
    rng = np.random.default_rng(2)
    n = np.full(40, 5_000)
    d = rng.binomial(n, 0.03)
    fit = pf.fit_rho(d, n)
    assert fit["rho"] < 0.002
    assert pf.mom_rho(d / n, n) < 0.002


def test_a_drifting_book_is_not_mistaken_for_correlation():
    years = 30
    t = np.arange(years) - (years - 1) / 2
    n = np.full(years, 50_000)
    p = norm.cdf(norm.ppf(0.03) - 0.03 * t)          # quality improves
    d = np.random.default_rng(3).binomial(n, p)
    assert pf.fit_rho(d, n)["rho"] > 0.01
    drift = pf.fit_rho(d, n, trend=True)
    assert drift["rho"] < 0.002
    assert drift["trend"] == pytest.approx(-0.03, abs=0.005)


def test_implied_factor_is_low_in_bad_years():
    d, n, z = history(0.08, years=60)
    f = pf.implied_factor(d, n, 0.03, 0.08)
    assert np.corrcoef(f, z)[0, 1] > 0.95


def test_loadings_of_one_shared_series_are_one():
    rng = np.random.default_rng(4)
    z = rng.standard_normal(50)
    same = pd.DataFrame({"a": z, "b": 2 * z, "c": z + 1})
    assert np.allclose(pf.loadings(same), 1.0)
    noise = pd.DataFrame({"a": z, "b": rng.standard_normal(50),
                          "c": rng.standard_normal(50)})
    assert pf.loadings(noise).min() < 0.5


# --------------------------------------------------- LGD in a draw

def test_lgd_line_passes_through_both_estimates():
    assert pf.lgd_in_draw(0.60, 0.70, 0.0) == pytest.approx(0.60)
    bad = -norm.ppf(pf.DOWNTURN_YEAR)
    assert pf.lgd_in_draw(0.60, 0.70, bad) == pytest.approx(0.70)
    assert pf.lgd_in_draw(0.95, 1.20, -5.0) == 1.0


def test_frye_jacobs_keeps_expected_loss_and_rises_in_bad_years():
    x = np.linspace(-9, 9, 4001)
    w = norm.pdf(x) * (x[1] - x[0])
    p, lgd, rho = 0.02, 0.6, 0.15
    dr = pf.conditional_pd(p, rho, x)
    lg = pf.frye_jacobs(p, lgd, rho, x)
    assert (w * dr * lg).sum() == pytest.approx(p * lgd, rel=1e-4)
    assert pf.frye_jacobs(p, lgd, rho, -3) > pf.frye_jacobs(p, lgd,
                                                            rho, 0)


# ---------------------------------------------------- simulation

def small_book():
    pools = pd.DataFrame({
        "product": ["card", "personal"], "band": ["all", "all"],
        "missed": [0, 0], "accounts": [5_000, 2_000],
        "ead": [5e8, 4e8], "pd": [0.03, 0.04], "n_eff": [5_000, 2_000],
        "lgd": [0.70, 0.65], "downturn": [0.72, 0.69],
        "cure_rate": [0.15, 0.16], "segment": ["card", "personal"]})
    names = pd.DataFrame({
        "company_id": [f"C{i:04d}" for i in range(40)],
        "grade": 6, "pd": np.linspace(0.005, 0.08, 40),
        "ead": np.linspace(1e8, 2e9, 40), "lgd": 0.6,
        "sector": ["a", "b"] * 20, "segment": "companies"})
    model = pf.Model(rho={"card": 0.02, "personal": 0.03,
                          "companies": 0.15},
                     beta={"card": 0.8, "personal": 0.8,
                           "companies": 0.3}, common=1.0)
    return pools, names, model


def test_simulated_mean_is_the_expected_loss():
    pools, names, model = small_book()
    r = pf.simulate(pools, names, model, n=60_000, chunk=7_000)
    el = pf.expected_loss(pools, names)
    assert r.el() == pytest.approx(el, rel=0.02)
    assert r.fine.mean() == pytest.approx(el, rel=0.02)
    assert r.es() > r.var() > r.el()


def test_simulation_repeats_and_contributions_add_up():
    pools, names, model = small_book()
    a = pf.simulate(pools, names, model, n=20_000)
    b = pf.simulate(pools, names, model, n=20_000)
    assert np.array_equal(a.total, b.total)
    pc, nc = a.contributions()
    assert pc.sum() + nc.sum() == pytest.approx(a.es(), rel=1e-6)
    by = a.by_segment.sum(axis=1).to_numpy()
    assert np.allclose(by, a.total)


def test_an_extra_name_leaves_the_book_unchanged():
    pools, names, model = small_book()
    extra = names.head(1).assign(company_id="X")
    a = pf.simulate(pools, names, model, n=10_000)
    b = pf.simulate(pools, names, model, n=10_000, extra=extra)
    assert np.array_equal(a.total, b.total)
    assert b.extra.shape == (10_000, 1)


def test_correlation_fattens_the_tail_not_the_mean():
    pools, names, model = small_book()
    hi = pf.Model(rho={k: 2 * v for k, v in model.rho.items()},
                  beta=model.beta)
    a = pf.simulate(pools, names, model, n=40_000)
    b = pf.simulate(pools, names, hi, n=40_000)
    assert b.el() == pytest.approx(a.el(), rel=0.03)
    assert b.var() > a.var()


def test_sectors_of_their_own_keep_the_average_correlation():
    pools, names, model = small_book()
    m = pf.with_sectors(model, names, 0.5)
    h = 0.5                                  # two equal sectors
    avg = m.rho["companies"] * (0.5 + 0.5 * h)
    assert avg == pytest.approx(model.rho["companies"])


# -------------------------------------------------- concentration

def test_hhi_and_effective_number():
    assert pf.hhi([1, 1, 1, 1]) == pytest.approx(0.25)
    assert pf.effective_number([5, 5]) == pytest.approx(2)
    assert pf.effective_number([9, 1]) < 2


def test_granularity_adjustment_shrinks_as_names_split():
    e = np.linspace(1, 10, 50)
    g1 = pf.granularity_adjustment(e, 0.6, 0.02, 0.15)
    g2 = pf.granularity_adjustment(np.repeat(e / 2, 2), 0.6, 0.02, 0.15)
    assert g1 > 0
    assert g2 == pytest.approx(g1 / 2, rel=0.01)


def test_granularity_adjustment_matches_a_simulation():
    rng = np.random.default_rng(5)
    names = pd.DataFrame({"company_id": [f"C{i}" for i in range(60)],
                          "pd": rng.uniform(0.005, 0.05, 60),
                          "ead": rng.uniform(1, 20, 60) * 1e8,
                          "lgd": 0.6, "sector": "a", "grade": 5,
                          "segment": "companies"})
    m = pf.Model(rho={"companies": 0.12}, beta={"companies": 1.0},
                 lgd_link=False)
    empty = small_book()[0].iloc[:0]
    r = pf.simulate(empty, names, m, n=200_000)
    fine = pf.one_factor_loss(empty, names, m)
    ga = pf.granularity_adjustment(names.ead, names.lgd, names["pd"],
                                   0.12)
    assert r.var() - fine == pytest.approx(ga, rel=0.35)


def test_the_module_never_reads_the_truth():
    src = inspect.getsource(pf)
    assert "truth=True" not in src and "TRUTH" not in src


# ------------------------------------------------ Fernhill's book

@needs_book
def test_default_history_has_the_decade():
    con = fernhill.connect()
    h = pf.default_history(con)
    com = h[h.segment == "companies"]
    assert list(com.year) == list(range(2017, 2026))
    assert com.defaults.sum() == 35
    assert set(pf.SEGMENTS) <= set(h.segment)


@needs_book
def test_book_reconciles_to_chapter_21():
    con = fernhill.connect()
    r = capital.load()
    pools, names = pf.book(con, r)
    live = r[~r.in_default.astype(bool)]
    retail = live[live.segment == "retail"]
    assert pools.ead.sum() == pytest.approx(retail.irb_ead.sum())
    assert pools.accounts.sum() == len(retail)
    assert len(names) == live[live.segment == "commercial"] \
        .company_id.nunique()
    assert (names.ead >= names.drawn).all()
    assert names.lgd.between(0, 1).all()
