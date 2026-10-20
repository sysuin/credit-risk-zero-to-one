"""Tests for ballast.market: the default point, Merton's equations
and their solution, distance to default, and spreads and hazards."""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pytest
from scipy.stats import norm

import fernhill
from ballast import market as mk
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


# ---------------------------------------------------- pure functions

def test_default_point_is_short_plus_half_long():
    assert mk.default_point(30, 40) == pytest.approx(50)
    assert mk.default_point(30, 40, weight=0) == pytest.approx(30)
    assert mk.default_point(30, 40, weight=1) == pytest.approx(70)


def test_accounts_arrive_at_the_end_of_march():
    assert mk.arrives(2019) == dt.date(2020, 3, 31)


def test_equity_is_a_call_on_the_assets():
    V, s, D, r = 100.0, 0.25, 80.0, 0.03
    E, sE = mk.equity_value(V, s, D, r)
    # Worth more than the assets less the discounted debt (a put's
    # worth more), less than the assets, and more volatile than them.
    assert V - D * math.exp(-r) < E < V
    assert sE > s
    # By hand: Black-Scholes with T = 1.
    d1 = (math.log(V / D) + r + s * s / 2) / s
    by_hand = V * norm.cdf(d1) - D * math.exp(-r) * norm.cdf(d1 - s)
    assert E == pytest.approx(by_hand, rel=1e-12)
    assert sE == pytest.approx(s * V * norm.cdf(d1) / by_hand)


@pytest.mark.parametrize("V, s, D, r", [
    (100.0, 0.25, 50.0, 0.02),      # safe
    (100.0, 0.30, 90.0, 0.04),      # leveraged
    (35.0, 0.22, 32.6, 0.0025),     # Alder Oak in October 2020
    (2e8, 0.40, 1e8, 0.0475),       # large and volatile
])
def test_solving_recovers_the_assets(V, s, D, r):
    E, sE = mk.equity_value(V, s, D, r)
    V2, s2, ok = mk.solve_assets(E, sE, D, r)
    assert ok
    assert V2 == pytest.approx(V, rel=1e-6)
    assert s2 == pytest.approx(s, rel=1e-6)


def test_distance_to_default_and_pd():
    dd = mk.distance_to_default(100.0, 0.2, 80.0, drift=0.05)
    assert dd == pytest.approx((math.log(1.25) + 0.05 - 0.02) / 0.2)
    assert mk.default_probability(dd) == pytest.approx(norm.cdf(-dd))
    # Further from the default point, or less volatile: further away.
    assert mk.distance_to_default(120.0, 0.2, 80.0, 0.05) > dd
    assert mk.distance_to_default(100.0, 0.1, 80.0, 0.05) > dd
    # A higher drift moves the distance up by drift / volatility.
    up = mk.distance_to_default(100.0, 0.2, 80.0, drift=0.07)
    assert up - dd == pytest.approx(0.02 / 0.2)


def test_risk_neutral_pd_is_n_of_minus_d2():
    V, s, D, r = 100.0, 0.3, 85.0, 0.02
    _, d2 = mk._d1_d2(V, s, D, r, 1.0)
    dd = mk.distance_to_default(V, s, D, r)
    assert dd == pytest.approx(d2)


def test_merton_spread():
    tight = mk.merton_spread_bps(500.0, 0.2, 50.0, 0.03)
    wide = mk.merton_spread_bps(100.0, 0.3, 80.0, 0.03)
    wider = mk.merton_spread_bps(100.0, 0.4, 80.0, 0.03)
    assert 0 <= tight < 0.01
    assert 0 < wide < wider


def test_hazard_and_pd_from_a_spread():
    h = mk.hazard_from_spread(300)
    assert h == pytest.approx(0.05)
    assert mk.hazard_from_spread(300, lgd=0.5) == pytest.approx(0.06)
    assert mk.pd_from_hazard(h) == pytest.approx(1 - math.exp(-0.05))
    assert mk.pd_from_hazard(h, 5) == pytest.approx(1 - math.exp(-0.25))


# ------------------------------------------------------ the loan book

@pytest.fixture(scope="module")
def con():
    return fernhill.connect()


@pytest.fixture(scope="module")
def panel(con):
    return mk.grade_in_force(con, mk.merton_panel(con))


@needs_book
def test_alder_oak_default_point(con):
    dp = mk.default_points(con)
    cid = con.execute(
        "SELECT company_id FROM companies "
        "WHERE name = 'Alder Oak Materials'").fetchone()[0]
    row = dp[(dp.company_id == cid) & (dp.fiscal_year == 2019)].iloc[0]
    assert row.short_term_debt + row.long_term_debt == row.total_debt
    assert row.default_point / 1e8 == pytest.approx(32.57, abs=0.005)


@needs_book
def test_every_listed_client_is_estimated(con, panel):
    n_listed = con.execute("SELECT count(*) FROM companies "
                           "WHERE listed").fetchone()[0]
    assert panel.company_id.nunique() == n_listed
    assert panel.converged.all()
    assert np.isfinite(panel.dd).all()
    assert (panel.sigma_a < panel.sigma_e).all()
    assert (panel.assets > panel.equity).all()


@needs_book
def test_no_month_uses_accounts_from_the_future(panel):
    used = [mk.arrives(int(fy)) for fy in panel.fiscal_year]
    assert all(a <= m for a, m in zip(used, panel.month))


@needs_book
def test_risk_free_is_the_policy_rate(con, panel):
    rates = dict(con.execute("SELECT month, policy_rate_pct / 100 "
                             "FROM market_rates").fetchall())
    assert all(r == pytest.approx(rates[m])
               for m, r in zip(panel.month, panel.r))


@needs_book
def test_grades_in_force_were_assigned_by_then(con, panel):
    first = dict(con.execute("""
        SELECT company_id, min(rating_date) FROM ratings
        WHERE internal_grade IS NOT NULL GROUP BY 1""").fetchall())
    graded = panel[panel.internal_grade.notna()]
    assert all(first[c] <= m for c, m in
               zip(graded.company_id, graded.month))
