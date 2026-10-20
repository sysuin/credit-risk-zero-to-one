"""Tests for ballast.ecl: the pieces of the expected-loss sum, the
staging rule, and a run on Fernhill's book at 31 December 2025."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast import ecl, loanmath
from ballast.config import LOANBOOK
from ballast.parameters import pd as pdm

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def test_balances_follow_the_schedule():
    s = loanmath.schedule(1_200_000, 9.9, 36)
    b = ecl.balances([1_200_000], [9.9], [36], 40)[0]
    assert np.allclose(b[:36], s["opening"], atol=50)
    assert (b[36:] == 0).all()


def test_balances_grow_in_free_months():
    s = loanmath.schedule(1_000_000, 2.5, 72, free_months=12)
    b = ecl.balances([1_000_000], [2.5], [72], 72, free=[12])[0]
    assert b[11] > b[0]
    assert np.allclose(b, s["opening"], atol=100)


def test_incidence_is_survival_times_hazard():
    h = np.array([[0.1, 0.1, 0.1]])
    x = np.array([[0.2, 0.2, 0.2]])
    m = ecl.incidence(h, x)[0]
    assert m == pytest.approx([0.1, 0.07, 0.049])
    assert m.sum() < 0.1 * 3


def test_lift_hits_the_twelve_month_target():
    h = np.full((3, 24), 0.002)
    x = np.full((3, 24), 0.01)
    target = np.array([0.01, 0.10, 0.60])
    out = ecl.lift(h, x, target)
    got = ecl.incidence(out[:, :12], x[:, :12]).sum(axis=1)
    assert got == pytest.approx(target, rel=1e-4)
    assert (out[:, 12:] == 0.002).all()


def test_sicr_needs_both_ratio_and_points():
    now = np.array([0.005, 0.03, 0.03, 0.10])
    orig = np.array([0.001, 0.02, 0.01, 0.06])
    assert ecl.sicr(now, orig, 2.0, 0.01).tolist() == [
        False, False, True, False]


def test_stage_reasons_in_order():
    f = pd.DataFrame({"in_default": [True, False, False, False, False],
                      "missed": [3, 1, 0, 0, 0],
                      "cured": [False, True, True, False, False],
                      "grade": [np.nan, np.nan, np.nan, 9, 4],
                      "pd12": [1.0, 0.3, 0.02, 0.1, 0.002],
                      "pd12_orig": [0.01, 0.01, 0.01, 0.1, 0.003]})
    s = ecl.stage(f)
    assert s["stage"].tolist() == [3, 2, 2, 2, 1]
    assert s["reason"].tolist() == ["default", "arrears", "cured",
                                    "watchlist", ""]


def test_cecl_path_reverts_to_the_long_run():
    u = np.linspace(6.0, 7.0, 60)
    p = ecl.path(u, 120, long_run=5.0)
    assert p[:ecl.CECL_RS_MONTHS] == pytest.approx(
        u[:ecl.CECL_RS_MONTHS])
    assert p[ecl.CECL_RS_MONTHS + ecl.CECL_REVERT:] == pytest.approx(5)
    held = ecl.path(u, 120)
    assert held[60:] == pytest.approx(7.0)


def test_commercial_year_one_is_the_master_scale():
    params = {"commercial": pdm.load_json("pd_commercial.json")}
    q = ecl.commercial_pd(params, [1, 8], 7)
    assert q[0, 0] == pytest.approx(0.0003)
    assert q[1, 0] == pytest.approx(0.05)
    assert q[1, 6] == pytest.approx(q[1, 4])
    assert (q > 0).all()


def test_fast_hazards_match_chapter_18():
    model = pdm.load_hazards()["card"]
    mob = np.array([[1, 5, 30, 100]])
    u = np.array([4.0, 5.0, 6.0, 7.0])
    fast = ecl.hazards(model, mob, np.array(["630-659"]), u)[0]
    slow = model.hazard(mob[0], "630-659", u)
    assert fast == pytest.approx(slow)


@pytest.fixture(scope="module")
def december():
    con = fernhill.connect()
    params = ecl.parameters(con)
    return con, params, ecl.run(con, ecl.AS_OF, params)


@needs_book
def test_every_open_account_once(december):
    con, _, r = december
    n = con.execute("""
        SELECT count(*) FROM performance WHERE month = ?
          AND status IN ('up_to_date', 'arrears', 'default')""",
                    [ecl.AS_OF]).fetchone()[0]
    f = con.execute("""SELECT count(DISTINCT facility_id)
                       FROM facility_months WHERE month = ?""",
                    [ecl.AS_OF]).fetchone()[0]
    assert len(r) == n + f
    assert r["account_id"].is_unique


@needs_book
def test_stage_three_is_default(december):
    _, _, r = december
    assert (r.loc[r["stage"] == 3, "in_default"]).all()
    assert (r["ecl"] >= 0).all()
    s1 = r[r["stage"] == 1]
    assert (s1["ecl12"] <= s1["ecl_life"] + 1e-6).all()


@needs_book
def test_weighted_above_base(december):
    _, _, r = december
    total = {s: r[f"ecl_{s}"].sum() for s in ecl.WEIGHTED}
    assert total["upside"] < total["base"] < total["downside"] \
        < total["severe"]
    assert r["ecl"].sum() > total["base"]


@needs_book
def test_cecl_above_ifrs9(december):
    con, params, r = december
    c = ecl.run(con, ecl.AS_OF, params, basis="cecl")
    assert c["ecl"].sum() > r["ecl"].sum()
