"""Tests for ballast.performance: the two definitions of default, the
stitching of migrated cards, vintages, roll rates and portfolio rates."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast import performance as perf
from ballast.config import LOANBOOK

D = dt.date
needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def months(start: dt.date, n: int) -> list[dt.date]:
    out, m = [], pd.Timestamp(start)
    for _ in range(n):
        out.append(m.date())
        m = m + pd.offsets.MonthEnd(1)
    return out


def rows(account, missed, arrears=None, balance=500_000,
         bankrupt=(), charged=()):
    """Month-end rows for flag_defaults from a list of missed counts."""
    arrears = arrears or [m * 40_000 for m in missed]
    return [(account, "personal", mo, m, a, balance, i in charged,
             i in bankrupt)
            for i, (mo, m, a) in enumerate(
                zip(months(D(2024, 1, 31), len(missed)), missed,
                    arrears))]


# ----------------------------------------------------- the definitions

def test_materiality_needs_both_thresholds():
    assert perf.material(10_001, 500_000)
    assert not perf.material(10_000, 500_000)       # $100 is not over
    assert not perf.material(50_000, 5_000_000)     # 1% is not over
    assert perf.material(50_001, 5_000_000)


def test_triggers():
    assert perf.trigger("dpd90", 3, 100, 500_000, False, False) \
        == "days_past_due"
    assert perf.trigger("dod2021", 3, 100, 500_000, False, False) is None
    assert perf.trigger("dod2021", 0, 0, 500_000, False, True) \
        == "bankruptcy"
    assert perf.trigger("dod2021", 6, 100, 500_000, True, False) \
        == "charged_off"
    assert perf.trigger("dpd90", 1, 0, 500_000, False, True) is None
    with pytest.raises(ValueError):
        perf.trigger("dpd60", 3, 0, 0, False, False)


def test_probation_holds_a_default_open():
    # PL0015999's pattern: 90, 120, cured, slipped twice, cured again
    r = rows("A", [0, 1, 2, 3, 4, 0, 0, 1, 2, 0, 0, 0])
    old = perf.flag_defaults(r, "dpd90")
    new = perf.flag_defaults(r, "dod2021")
    assert len(old) == len(new) == 1
    assert old[0][2] == new[0][2] == D(2024, 4, 30)
    assert old[0][5] == D(2024, 6, 30)       # first clean month
    assert new[0][5] == D(2024, 12, 31)      # third clean in a row


def test_re_default_inside_probation_is_one_episode():
    r = rows("A", [3, 0, 3, 0, 0, 0])
    assert len(perf.flag_defaults(r, "dpd90")) == 2
    assert len(perf.flag_defaults(r, "dod2021")) == 1


def test_immaterial_arrears_wait_until_material():
    missed = [1, 2, 3, 4, 5]
    arrears = [2_500, 5_000, 7_500, 10_000, 12_500]   # $25 minimums
    r = rows("C", missed, arrears, balance=100_000)
    old = perf.flag_defaults(r, "dpd90")
    new = perf.flag_defaults(r, "dod2021")
    assert old[0][2] == D(2024, 3, 31)
    assert new[0][2] == D(2024, 5, 31)


def test_bankruptcy_without_arrears_is_a_default():
    r = rows("B", [0, 0, 0, 0], bankrupt={1})
    assert perf.flag_defaults(r, "dpd90") == []
    ep = perf.flag_defaults(r, "dod2021")
    assert ep[0][3] == "bankruptcy" and ep[0][5] is None


def test_each_account_starts_clean():
    r = rows("A", [3, 3]) + rows("B", [0, 3])
    ep = perf.flag_defaults(r, "dpd90")
    assert [e[0] for e in ep] == ["A", "B"]


# ------------------------------------------------------- the real book

@pytest.fixture(scope="module")
def con():
    if not LOANBOOK.exists():
        pytest.skip("no loan book")
    c = fernhill.connect()
    perf.prepare(c)
    return c


@pytest.fixture(scope="module")
def naive(con):
    return {d: perf.default_episodes(con, d, stitched=False)
            for d in perf.DEFINITIONS}


@pytest.fixture(scope="module")
def stitched(con):
    return {d: perf.default_episodes(con, d, stitched=True)
            for d in perf.DEFINITIONS}


def _keys(df, lo, hi):
    y = pd.to_datetime(df["default_month"]).dt.year
    df = df[(y >= lo) & (y <= hi)]
    return set(zip(df["account_id"], pd.to_datetime(df["default_month"])))


@needs_book
def test_recompute_matches_the_recorded_table(con, naive):
    rec = con.execute("SELECT account_id, default_month, definition "
                      "FROM defaults").df()
    old = _keys(rec[rec["definition"] == "dpd90"], 2016, 2020)
    assert _keys(naive["dpd90"], 2016, 2020) == old
    new = _keys(rec[rec["definition"] == "dod2021"], 2021, 2025)
    ours = _keys(naive["dod2021"], 2021, 2025)
    # only accounts whose default straddled 1 January 2021 differ
    differ = ours ^ new
    assert len(differ) == 24
    assert all(m < pd.Timestamp(2021, 4, 1) for _, m in differ)


@needs_book
def test_every_migrated_card_has_a_cc_root(con):
    n, odd = con.execute("""
        SELECT count(*), count(*) FILTER (
            WHERE root_id NOT LIKE 'CC%' OR root_open > open_date)
        FROM account_root WHERE account_id LIKE 'CK%'""").fetchone()
    assert n == 10_050 and odd == 0
    h = perf.stitched_history(con, "CK0000001")
    assert h["account_id"].iloc[0] == "CC0000002"
    assert pd.to_datetime(h["month"]).diff().dt.days.max() <= 31


@needs_book
def test_stitching_removes_the_double_counts(naive, stitched):
    assert len(naive["dod2021"]) - len(stitched["dod2021"]) == 60
    assert not stitched["dod2021"]["account_id"].str.startswith(
        "CK").any()


@needs_book
def test_vintages_rise_and_stop_where_unseen(con, stitched):
    t = perf.vintage_table(con, "personal", stitched["dod2021"])
    curves = t.drop(columns="accounts")
    for _, row in curves.iterrows():
        seen = row.dropna().to_numpy()
        assert (np.diff(seen) >= 0).all()
    assert np.isnan(t.loc["2025", 12]) and not np.isnan(t.loc["2024", 12])
    assert t.loc["2024", "accounts"] == 3_011


@needs_book
def test_vintages_refuse_mixed_stitching(con, naive):
    with pytest.raises(ValueError):
        perf.vintage_table(con, "card", naive["dod2021"], stitched=True)


@needs_book
def test_emergency_loans_clock(con, stitched):
    eps = stitched["dod2021"]
    by_open = perf.vintage_table(con, "sme_emergency", eps)
    by_due = perf.vintage_table(con, "sme_emergency", eps, clock="due")
    assert by_open.loc["2020", 12] == 0.0
    assert by_due.loc["2020", 12] > 0.1


@needs_book
def test_transition_matrix_rows_are_shares(con):
    m = perf.transition_matrix(con, "personal", D(2023, 1, 31),
                               D(2025, 11, 30))
    shares = m.drop(columns="n")
    assert np.allclose(shares.sum(axis=1), 1.0)
    assert list(m.index) == perf.BUCKETS[:6]
    one = perf.project(m, 1)
    assert np.allclose(one[shares.columns].to_numpy(), shares.to_numpy())
    year = perf.project(m, 12)
    assert np.allclose(year.sum(axis=1), 1.0)
    flow = perf.flow_to_loss(m)
    assert (np.diff(flow["to_loss"].to_numpy()) > 0).all()


@needs_book
def test_portfolio_rates_reconcile_with_chapter_one(con, stitched):
    r = perf.portfolio_rates(con, "personal", 2024, stitched["dod2021"])
    assert round(r["written_off"] / 100) == 1_706_057    # Chapter 1
    assert 0 < r["default_rate"] < 0.1 and r["at_risk"] <= r["open_1jan"]
