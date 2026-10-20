"""Tests for ballast.parameters.lgd: discounting, the floor and cures,
the recovery triangle and the two ways of finishing it, and the
workouts built from Fernhill's loan book."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast.config import LOANBOOK
from ballast.parameters import lgd

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")
T = pd.Timestamp


def toy():
    """Three workouts: written off, cured, and still open."""
    w = pd.DataFrame({
        "workout": [0, 1, 2],
        "product": ["card"] * 3,
        "default_month": [T("2020-01-31"), T("2020-03-31"),
                          T("2025-10-31")],
        "end_month": [T("2020-04-30"), T("2020-06-30"), pd.NaT],
        "outcome": ["written_off", "cured", "open"],
        "ead_cents": [100_000, 50_000, 80_000],
    })
    f = pd.DataFrame({
        "workout": [0, 0, 0, 1, 1, 2],
        "month": [T("2020-02-29"), T("2021-01-31"), T("2021-01-31"),
                  T("2020-04-30"), T("2020-06-30"), T("2025-11-30")],
        "kind": ["payment", "collections_payment", "cost", "payment",
                 "cure", "payment"],
        "amount_cents": [10_000, 24_000, -4_000, 5_000, 30_000, 2_000],
        "months": [1, 12, 12, 1, 3, 1],
    })
    return w, f


def test_discounting_matches_present_value():
    w, f = toy()
    rates = pd.Series(12.0, index=w["workout"])     # 1% a month
    v = lgd.discounted(f, rates)
    assert v.iloc[0] == pytest.approx(10_000 / 1.01)
    assert v.iloc[1] == pytest.approx(24_000 / 1.01 ** 12)


def test_realised_lgd_floor_and_cure():
    w, f = toy()
    out = lgd.realised(w, f).set_index("workout")
    assert out.loc[0, "lgd"] == pytest.approx(0.70)    # 1 - 30k/100k
    assert out.loc[1, "lgd"] == 0.0                   # a cure loses 0
    big = f.copy()
    big.loc[1, "amount_cents"] = 500_000              # recovers > EAD
    assert lgd.realised(w, big).set_index("workout").loc[0, "lgd"] == 0


def test_no_exposure_means_no_lgd():
    w, f = toy()
    w.loc[2, "ead_cents"] = 0
    out = lgd.realised(w, f)
    assert np.isnan(out.loc[2, "lgd"])
    assert lgd.pooled(out)["workouts"].iloc[0] == 2


def test_as_at_reopens_later_endings():
    w, _ = toy()
    then = lgd.as_at(w, "2020-05-31")
    assert list(then["workout"]) == [0, 1]
    assert then.set_index("workout").loc[1, "outcome"] == "open"


def test_triangle_caps_masks_and_cures():
    w, f = toy()
    rates = pd.Series(0.0, index=w["workout"])
    tri = lgd.recovery_triangle(w, f, rates, max_months=12)
    row = tri.loc["2020"]
    # month 1: 10k + 5k of 150k; month 3: the cure counts in full
    assert row[1] == pytest.approx(15_000 / 150_000)
    assert row[3] == pytest.approx((10_000 + 50_000) / 150_000)
    assert row[12] == pytest.approx((30_000 + 50_000) / 150_000)
    assert tri.loc["2025"].isna().sum() == 10        # seen 2 months


def hand_triangle():
    tri = pd.DataFrame({0: [0.1, 0.1, 0.0], 1: [0.3, 0.2, np.nan],
                        2: [0.4, np.nan, np.nan]},
                       index=["2019", "2020", "2021"])
    tri.attrs["ead"] = pd.Series(1.0, index=tri.index)
    return tri


def test_chain_ladder_and_additive():
    tri = hand_triangle()
    fac = lgd.development_factors(tri)
    assert fac[0] == pytest.approx(0.5 / 0.2)
    assert fac[1] == pytest.approx(0.4 / 0.3)
    chain = lgd.complete(tri, "chain")
    assert chain["2020"] == pytest.approx(0.2 * 0.4 / 0.3)
    assert chain["2021"] == 0.0           # nothing to multiply
    add = lgd.complete(tri, "additive")
    assert add["2020"] == pytest.approx(0.2 + 0.1)
    assert add["2021"] == pytest.approx(0.0 + 0.15 + 0.1)


@needs_book
def test_workouts_reconcile_with_the_book():
    con = fernhill.connect()
    w = lgd.workouts(con)
    assert len(w) == 6321                 # Chapter 6's episodes
    assert set(w["outcome"]) <= set(lgd.OUTCOMES)
    f = lgd.cash_flows(con, w)
    rec = f[~f["kind"].isin(["payment", "cure"])]
    total = con.execute("""SELECT count(*), sum(r.amount_cents)
        FROM recoveries r JOIN accounts a USING (account_id)""").fetchone()
    assert (len(rec), rec["amount_cents"].sum()) == total
    # every recovery belongs to a written-off workout
    kinds = rec["workout"].map(w.set_index("workout")["outcome"])
    assert (kinds == "written_off").all()


@needs_book
def test_guarantee_and_lgd_ranges():
    con = fernhill.connect()
    w = lgd.workouts(con)
    f = lgd.cash_flows(con, w)
    g = f[f["kind"] == "guarantee"].merge(
        w[["workout", "product", "ead_cents"]], on="workout")
    em = g[g["product"] == "sme_emergency"]
    share = em.groupby("workout")["amount_cents"].sum() \
        / em.groupby("workout")["ead_cents"].first()
    assert share.median() == pytest.approx(0.80, abs=0.005)
    done = lgd.realised(w, f, lgd.discount_rates(con, w))
    done = done[done["default_month"] <= "2021-12-31"]
    est = lgd.pooled(done)["lgd"]
    assert est["card"] > est["auto"] > est["mortgage"]
    assert 0.5 < est["personal"] < 0.8
