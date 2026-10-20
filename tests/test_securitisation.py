"""Tests for ballast.securitisation: the pool's schedules, the
projection, the waterfall, the Monte Carlo, the illustrative capital
rule, and the credit-protection and swap-exposure arithmetic."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import fernhill
from ballast import securitisation as sec
from ballast.config import LOANBOOK, SEED
from ballast.parameters import pd as pdm

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def _deal(n=200, hazard=0.005, smm=0.0, months=36, seed=SEED):
    """A made-up pool of level-payment loans with a constant monthly
    default hazard and prepayment rate."""
    rng = np.random.default_rng(seed)
    bal = rng.integers(500_000, 3_000_000, n).astype(float)
    rate = rng.uniform(6, 12, n)
    r = rate / 1200
    pay = np.round(bal * r / (1 - (1 + r) ** -months))
    loans = pd.DataFrame({
        "account_id": [f"T{i:04d}" for i in range(n)],
        "balance_cents": bal, "rate_pct": rate, "payment_cents": pay,
        "mob": 1, "band": "all", "collateral_value_cents": bal * 1.5,
        "index_open": 100.0})
    loans["remaining"] = sec.remaining_payments(bal, rate, pay)
    z = float(np.log(hazard / (1 - hazard)))
    hm = pdm.HazardModel("auto", ["all"], [0], {"const": z, "u": 0.0},
                         {"const": -50.0})
    curve = pd.DataFrame({"smm": [smm]}, index=[1])
    flat = (np.full(60, 5.0), np.full(60, 100.0))
    paths = {"base": flat, "long_run": flat}
    return sec.Deal(loans, sec.schedules(loans), hm, curve,
                    (0.05, 0.40), 0.15, 3.0, 3.0, paths)


def _flows(T=12, interest=10.0, defaults=None, recoveries=None,
           pool=1200.0):
    """One deal's monthly flows: the pool repays evenly, less what
    defaults."""
    d = np.zeros(T) if defaults is None else np.asarray(defaults, float)
    r = np.zeros(T) if recoveries is None else np.asarray(recoveries,
                                                          float)
    sched = np.full(T, (pool - d.sum()) / T)
    bal = pool - np.r_[0, np.cumsum(sched + d)[:-1]]
    return {"balance": bal, "interest": np.full(T, interest),
            "scheduled": sched, "prepaid": np.zeros(T),
            "defaulted": d, "recovered": r}


NOTES = [("A", 900.0, 4.0), ("B", 200.0, 6.0), ("C", 100.0, None)]


# ------------------------------------------------------ no loan book

def test_remaining_payments_recovers_the_term():
    r = 9.0 / 1200
    pay = 1_000_000 * r / (1 - (1 + r) ** -48)
    assert sec.remaining_payments(1_000_000, 9.0, pay) == 48


def test_schedules_amortise_to_zero():
    d = _deal()
    assert (d.sched[:, 0] == d.loans["balance_cents"]).all()
    assert (np.diff(d.sched, axis=1) <= 0).all()
    assert (d.sched[:, -1] == 0).all()


def test_projection_without_default_or_prepayment_is_the_schedule():
    d = _deal(hazard=1e-12, smm=0.0)
    cf = sec.project(d)
    want = (d.sched[:, :-1] - d.sched[:, 1:]).sum(0)
    np.testing.assert_allclose(cf["scheduled"].to_numpy()[:len(want)],
                               want, rtol=1e-6)
    assert cf["defaulted"].sum() < 1


def test_projection_accounts_for_every_dollar():
    d = _deal(hazard=0.01, smm=0.02)
    cf = sec.project(d)
    out = cf.scheduled + cf.prepaid + cf.defaulted
    nxt = cf.balance.shift(-1, fill_value=0.0)
    np.testing.assert_allclose(cf.balance, out + nxt, atol=1e-3)
    assert out.sum() == pytest.approx(d.loans.balance_cents.sum())


def test_recoveries_arrive_after_the_lag_less_lgd():
    d = _deal(hazard=0.01)
    cf = sec.project(d)
    assert cf.recovered.iloc[:sec.RECOVERY_LAG].sum() == 0
    assert 0 < cf.recovered.sum() < cf.defaulted.sum()


def test_waterfall_pays_out_every_dollar_it_receives():
    f = _flows(defaults=np.r_[np.zeros(5), 30, np.zeros(6)],
               recoveries=np.r_[np.zeros(8), 20, np.zeros(3)])
    w = sec.waterfall(f, NOTES)
    cash_in = sum(f[k].sum() for k in ("interest", "recovered",
                                       "scheduled", "prepaid"))
    cash_out = (w["fee"].sum() + w["residual"].sum()
                + sum(w["interest"][n].sum() + w["principal"][n].sum()
                      for n in w["names"]))
    assert cash_out == pytest.approx(cash_in)


def test_principal_is_paid_senior_first():
    w = sec.waterfall(_flows(), NOTES)
    paid_a = np.cumsum(w["principal"]["A"])
    first_b = np.flatnonzero(w["principal"]["B"] > 0)[0]
    assert paid_a[first_b] == pytest.approx(900)
    assert (w["principal"]["C"][:first_b] == 0).all()


def test_excess_spread_covers_small_losses_first():
    f = _flows(defaults=np.r_[5.0, np.zeros(11)])
    w = sec.waterfall(f, NOTES)
    assert all(w["loss"][n] == pytest.approx(0) for n in w["names"])
    assert w["pdl_credit"].sum() == pytest.approx(5.0)


def test_large_losses_hit_the_junior_notes_first():
    f = _flows(interest=0.0, defaults=np.r_[150.0, np.zeros(11)])
    w = sec.waterfall(f, NOTES, servicing_pct=0.0)
    assert w["loss"]["C"] == pytest.approx(100.0)
    assert w["loss"]["B"] == pytest.approx(50.0)
    assert w["loss"]["A"] == pytest.approx(0.0)
    assert w["pdl"][..., -1] == pytest.approx(150.0)


def test_waterfall_runs_many_deals_at_once():
    f = _flows(defaults=np.r_[150.0, np.zeros(11)])
    g = _flows()
    many = {k: np.vstack([f[k], g[k]]) for k in f}
    w = sec.waterfall(many, NOTES)
    one = sec.waterfall(f, NOTES)
    assert w["loss"]["C"][0] == pytest.approx(one["loss"]["C"])
    assert w["loss"]["C"][1] == pytest.approx(0.0)


def test_attachment_and_tranche_loss():
    att = sec.attachment()
    assert att["C"][0] == 0.0 and att["A"][1] == 1.0
    assert att["B"] == (att["C"][1], att["A"][0])
    a, d = 0.02, 0.07
    np.testing.assert_allclose(
        sec.tranche_loss([0.01, 0.02, 0.045, 0.07, 0.5], a, d),
        [0, 0, 0.5, 1, 1])


def test_vasicek_keeps_the_average_pd():
    z = np.linspace(-8, 8, 20001)
    w = norm.pdf(z) * (z[1] - z[0])
    for p in (0.01, 0.05):
        assert (sec.vasicek_pd(p, 0.2, z) * w).sum() == pytest.approx(
            p, rel=1e-4)
    assert sec.vasicek_pd(0.05, 0.2, -2) > 0.05 > sec.vasicek_pd(
        0.05, 0.2, 2)


def test_monte_carlo_mean_matches_the_projection():
    d = _deal(n=300, hazard=0.004, smm=0.015)
    total = d.loans.balance_cents.sum()
    cf = sec.simulate(d, 3000, 0.1, SEED)
    det = sec.project(d, "long_run")
    assert cf["defaulted"].sum(1).mean() == pytest.approx(
        det.defaulted.sum(), rel=0.05)
    assert sec.pool_loss(cf, total).mean() == pytest.approx(
        (det.defaulted - det.recovered).sum() / total, rel=0.08)


def test_correlation_fattens_the_tail_not_the_mean():
    d = _deal(n=300, hazard=0.004)
    total = d.loans.balance_cents.sum()
    lo = sec.pool_loss(sec.simulate(d, 3000, 0.02, SEED), total)
    hi = sec.pool_loss(sec.simulate(d, 3000, 0.30, SEED), total)
    assert hi.mean() == pytest.approx(lo.mean(), rel=0.1)
    assert np.quantile(hi, 0.99) > np.quantile(lo, 0.99)


def test_illustrative_capital():
    assert sec.illustrative_capital({"A": 1, "B": 1, "C": 1}) == \
        pytest.approx(sec.CAPITAL_PCT / 100)
    assert sec.illustrative_capital({"C": 1}) == pytest.approx(0.02)
    v = sec.RETAIN_VERTICAL
    assert sec.illustrative_capital({"A": v, "B": v, "C": v}) == \
        pytest.approx(v * sec.CAPITAL_PCT / 100)


def test_cds_cost_is_the_credit_triangle():
    c = sec.cds_cost(1e8, 300.0)
    assert c["premium_a_year"] == pytest.approx(3e6)
    assert c["hazard"] == pytest.approx(0.03 / 0.6)
    assert c["payout_if_default"] == pytest.approx(6e7)


def test_swap_exposure_and_cva():
    paths = sec.swap_rate_paths(3.0, 0.7, 60, 4000, SEED)
    v = sec.swap_values(paths, 3.0, 5, 1e7)
    assert np.allclose(v[:, 0], 0) and np.allclose(v[:, -1], 0)
    ee, pfe = sec.exposure_profile(v)
    assert (ee >= 0).all() and (pfe >= ee - 1e-9).all()
    assert 0 < ee.argmax() < 60
    np.testing.assert_allclose(sec.swap_values(paths, 3.0, 5, 1e7,
                                               receive_fixed=False), -v)
    assert sec.cva(ee, 0.0, 3.0) == 0.0
    assert sec.cva(ee, 300.0, 3.0) > sec.cva(ee, 30.0, 3.0) > 0


def test_never_reads_the_truth():
    src = Path(sec.__file__).read_text()
    assert "truth" not in src.replace("truth database", "")


# ------------------------------------------------------- loan book

@pytest.fixture(scope="module")
def deal():
    return sec.inputs(fernhill.connect())


@needs_book
def test_pool_holds_only_eligible_loans(deal):
    p = deal.loans
    assert len(p) == 4896
    assert (p["mob"] >= 1).all() and (p["balance_cents"] > 0).all()
    assert (p["remaining"] >= 1).all()
    assert set(p["band"]) == {"<600", "600-629", "630-659", "660+"}


@needs_book
def test_prepayment_curve_is_plausible(deal):
    c = deal.prepay
    assert ((c["smm"] > 0) & (c["smm"] < 0.05)).all()


@needs_book
def test_car_lgd_line_is_chapter_19s(deal):
    a, b = deal.lgd_line
    assert a == pytest.approx(0.055, abs=0.001)
    assert b == pytest.approx(0.419, abs=0.001)


@needs_book
def test_severe_loses_more_than_base(deal):
    base, severe = sec.project(deal, "base"), sec.project(deal,
                                                          "severe")
    assert severe.defaulted.sum() > base.defaulted.sum()
    total = deal.loans.balance_cents.sum()
    assert (base.scheduled + base.prepaid + base.defaulted).sum() == \
        pytest.approx(total)
