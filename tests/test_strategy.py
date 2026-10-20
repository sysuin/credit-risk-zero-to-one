"""Tests for ballast.decision.strategy: curves, swap sets, cut-offs,
refer bands, break-even and test sizes."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from ballast.config import LOANBOOK
from ballast.decision import strategy


@pytest.fixture
def book():
    """Scores whose expected bad rate falls as the score rises."""
    rng = np.random.default_rng(11)
    score = rng.integers(500, 650, 20_000)
    p = 1 / (1 + np.exp((score - 520) / 20))
    return score, p


def test_curve_trades_approvals_for_bad_rate(book):
    score, p = book
    c = strategy.curve(score, p, range(520, 621, 10))
    assert (np.diff(c["approval"]) < 0).all()
    assert (np.diff(c["bad_rate"]) < 0).all()
    assert (np.diff(c["marginal"]) < 0).all()
    # The marginal band is always riskier than the approved average.
    assert (c["marginal"] > c["bad_rate"]).all()
    row = c.iloc[0]
    assert row["approval"] == pytest.approx((score >= 520).mean())
    assert row["bads"] == pytest.approx(p[score >= 520].sum())


def test_choose_cutoff_takes_the_lowest_within_both_limits(book):
    score, p = book
    c = strategy.curve(score, p, range(520, 621))
    cut = strategy.choose_cutoff(c, max_bad_rate=0.10,
                                 max_marginal=0.20)
    ok = c[(c["bad_rate"] <= 0.10) & (c["marginal"] <= 0.20)]
    assert cut == ok["cutoff"].min()
    below = c[c["cutoff"] == cut - 1].iloc[0]
    assert below["bad_rate"] > 0.10 or below["marginal"] > 0.20
    with pytest.raises(ValueError):
        strategy.choose_cutoff(c, max_bad_rate=0.0, max_marginal=0.0)


def test_cutoff_for_share(book):
    score, _ = book
    cut = strategy.cutoff_for_share(score, 0.6)
    assert abs((score >= cut).mean() - 0.6) < 0.01


def test_refer_band_holds_no_more_than_the_share(book):
    score, _ = book
    w = strategy.refer_band(score, 580, 0.10)
    held = ((score >= 580 - w) & (score < 580 + w)).mean()
    wider = ((score >= 579 - w) & (score < 581 + w)).mean()
    assert held <= 0.10 < wider


def test_swap_set_counts_and_rates():
    a = np.array([1, 1, 0, 0, 1, 0], bool)
    b = np.array([1, 0, 1, 0, 1, 0], bool)
    y = np.array([0, 1, np.nan, 1, 1, 0])
    t = strategy.swap_set(a, b, y, promised=np.full(6, 0.1))
    assert t["n"].tolist() == [2, 1, 1, 2]
    assert t["known"].tolist() == [2, 1, 0, 2]
    assert t.loc["both approve", "bad_rate"] == 0.5
    assert np.isnan(t.loc["only B approves", "bad_rate"])
    assert t["n"].sum() == 6


def test_top_share_approves_exactly_that_many():
    s = np.array([5, 1, 4, 4, 2, 3])
    got = strategy.top_share(s, 0.5)
    assert got.sum() == 3 and got[0] and got[2] and got[3]


def test_break_even():
    odds, rate = strategy.break_even(good_earns=1_000, bad_costs=6_000)
    assert odds == 6 and rate == pytest.approx(1 / 7)


def test_n_per_arm_matches_the_formula():
    n = strategy.n_per_arm(0.10, 0.05)
    z = 1.959964 + 0.841621
    want = math.ceil(z ** 2 * (0.09 + 0.0475) / 0.05 ** 2)
    assert n == want
    assert strategy.n_per_arm(0.03, 0.025) > 10 * n


def test_detectable_is_the_inverse_of_n_per_arm():
    n = strategy.n_per_arm(0.12, 0.08)
    p2 = strategy.detectable(0.12, n)
    assert p2 == pytest.approx(0.08, abs=0.002)
    assert strategy.detectable(0.12, 10 * n) > p2


def test_months_to_run():
    assert strategy.months_to_run(1200, 200, 0.5) == 12 + 12 + 1


def test_loan_economics_adds_up():
    """Reads the loan book: profit is money back less money out."""
    if not LOANBOOK.exists():
        pytest.skip("no loan book")
    import fernhill
    d = strategy.loan_economics(fernhill.connect(), "personal")
    assert d["account_id"].is_unique
    done = d[d["close_reason"].isin(["repaid", "prepaid"])]
    back = done["paid"] + done["recovered"]
    want = back - done["amount_cents"] - done["funding"] - done["opex"]
    assert (done["profit"] - want).abs().max() <= 2
    assert (done["profit"] > 0).mean() > 0.9
    assert isinstance(d, pd.DataFrame)
