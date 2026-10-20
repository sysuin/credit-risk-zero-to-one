"""Tests for ballast.collections: the ladder, entries to arrears, the
cure model, the 2024 test's arithmetic, forbearance flags and the
debt-sale pools."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast import collections as coll
from ballast.config import AS_OF, LOANBOOK, SEED

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


@pytest.fixture(scope="module")
def con():
    return fernhill.connect()


# ------------------------------------------------------ no loan book

def test_ladder_follows_fernhills_policy():
    assert coll.ladder_action(0) is None
    assert [coll.ladder_action(m) for m in range(1, 8)] == [
        "reminder", "phone_call", "final_notice", "final_notice",
        "agency_referral", "agency_referral", "agency_referral"]


def test_difference_in_proportions():
    d, lo, hi = coll.diff_in_proportions(50, 100, 40, 100)
    assert d == pytest.approx(0.10)
    se = np.sqrt(0.5 * 0.5 / 100 + 0.4 * 0.6 / 100)
    assert hi - d == pytest.approx(1.96 * se)
    assert d - lo == pytest.approx(1.96 * se)


def test_standardised_difference():
    a = pd.Series([1.0, 2.0, 3.0, 4.0])
    assert coll.smd(a, a) == 0.0
    assert coll.smd(a + 1, a) > 0 > coll.smd(a, a + 1)


def test_present_value():
    assert coll.present_value([100, 100], [0, 12], 0.0) == 200
    assert coll.present_value([110], [12], 0.10) == pytest.approx(100)


def test_model_recovers_a_planted_effect():
    rng = np.random.default_rng(SEED)
    n = 4000
    df = pd.DataFrame({
        "bureau_v3": rng.normal(660, 50, n), "no_file": 0,
        "log_balance": rng.normal(8, 1, n),
        "months_on_book": rng.integers(1, 60, n),
        "behind_12m": rng.integers(0, 3, n), "part_paid": 0,
        "unemployment_pct": 5.0, "product": "personal"})
    logit = -5 + 0.8 * df["bureau_v3"] / 100
    df["cured_3m"] = (rng.random(n) < 1 / (1 + np.exp(-logit))
                      ).astype(int)
    m = coll.fit(df, "cured_3m", ["bureau_v3", "log_balance"])
    assert m.table().loc["bureau_v3", "coef"] == pytest.approx(0.8,
                                                               abs=0.2)
    p = coll.predict(m, df)
    assert p.mean() == pytest.approx(df["cured_3m"].mean(), abs=0.01)


def test_module_never_reads_the_truth():
    src = Path(coll.__file__).read_text()
    assert "truth=True" not in src and "truth.duckdb" not in src


# ------------------------------------------------------- loan book

@needs_book
def test_entries_are_fresh_and_complete(con):
    e = coll.entries(con, "2023-01-01", "2023-12-31")
    assert len(e) > 1000
    assert e["month"].max() <= pd.Timestamp(AS_OF) - pd.offsets.MonthEnd(3)
    assert set(e["cured_1m"]) <= {0, 1}
    assert 0.2 < e["rolled_90"].mean() < 0.5
    assert e["cured_1m"].mean() < e["cured_3m"].mean()
    row = e.iloc[0]
    prev = con.execute("""
        SELECT missed FROM performance WHERE account_id = ?
          AND month = last_day(?::DATE - INTERVAL 1 MONTH)""",
        [row["account_id"], row["month"].date()]).fetchone()
    assert prev == (0,)


@needs_book
def test_test_accounts_one_row_each_and_both_arms(con):
    t = coll.test_accounts(con)
    assert t["root_id"].is_unique
    assert set(t["arm"]) == {"call_first", "sms_first"}
    assert t["month"].dt.year.eq(2024).all()
    assert abs(t["call"].mean() - 0.5) < 0.05
    acts = con.execute("""SELECT DISTINCT test_arm, action FROM collections
                          WHERE test_arm IS NOT NULL""").fetchall()
    assert {(a, coll.TEST_ACTIONS[a]) for a, _ in acts} == set(acts)


@needs_book
def test_sales_paid_their_price(con):
    for sale, price in coll.SALES.items():
        pool = coll.sale_pool(con, sale)
        sold = pool[pool["sold"]]
        ratio = sold["price_cents"].sum() / sold["owed_cents"].sum()
        assert ratio == pytest.approx(price, abs=0.001)
        assert 0.05 < (~pool["sold"]).mean() < 0.30
        assert (pool.loc[~pool["sold"], "price_cents"] == 0).all()


@needs_book
def test_forbearance_flags_cover_every_holiday_month(con):
    f = coll.forborne(con, probation=24)
    hol = con.execute("SELECT count(*) FROM performance "
                      "WHERE payment_holiday").fetchone()[0]
    assert int(f["on_holiday"].sum()) == hol
    assert pd.Timestamp(f["month"].max()) <= pd.Timestamp("2023-03-31")


@needs_book
def test_worklist_treats_one_in_ten_as_challenger(con):
    hist = coll.entries(con, "2022-01-01", "2023-12-31")
    m = coll.fit(hist, "cured_3m")
    w = coll.worklist(con, dt.date(2025, 6, 30), m, seed=SEED)
    assert len(w) > 50
    assert w["p_cure"].is_monotonic_increasing
    share = w["treatment"].eq("sms_first").mean()
    assert 0.0 < share < 0.25
    assert set(w["first_action"]) <= {"phone_call", "sms"}
