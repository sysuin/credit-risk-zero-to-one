"""Tests for ballast.loanmath, the arithmetic of a loan (Ballast v0.1)."""
from __future__ import annotations

import pytest

from ballast import loanmath as lm
from ballast.config import LOANBOOK

# PL0000001: $15,100 over 60 months at 10.9%, booked at $327.56.
AMOUNT, RATE, TERM = 1_510_000, 10.9, 60


def test_payment_matches_the_booked_loan():
    assert lm.monthly_payment(AMOUNT, RATE, TERM) == 32_756


def test_payment_at_zero_rate_is_principal_over_term():
    assert lm.monthly_payment(120_000, 0.0, 12) == 10_000


def test_payment_free_months_grow_the_balance_first():
    grown = 1_000_000 * (1 + 2.5 / 1200) ** 12
    assert lm.monthly_payment(1_000_000, 2.5, 72, free_months=12) == \
        lm.monthly_payment(round(grown), 2.5, 60)
    s = lm.schedule(1_000_000, 2.5, 72, free_months=12)
    assert (s["payment"].iloc[:12] == 0).all()
    assert s["closing"].iloc[11] > 1_000_000
    assert s["closing"].iloc[-1] == 0
    assert len(s) == 72


def test_schedule_repays_exactly_the_principal():
    s = lm.schedule(AMOUNT, RATE, TERM)
    assert len(s) == TERM
    assert s["principal"].sum() == AMOUNT
    assert s["closing"].iloc[-1] == 0
    assert (s["interest"] + s["principal"] == s["payment"]).all()
    assert (s["opening"] - s["principal"] == s["closing"]).all()


def test_schedule_interest_falls_and_principal_rises():
    s = lm.schedule(AMOUNT, RATE, TERM)
    assert s["interest"].is_monotonic_decreasing
    assert s["principal"].iloc[:-1].is_monotonic_increasing


def test_schedule_last_payment_absorbs_the_rounding():
    s = lm.schedule(AMOUNT, RATE, TERM)
    assert (s["payment"].iloc[:-1] == 32_756).all()
    assert abs(s["payment"].iloc[-1] - 32_756) < TERM


def test_schedule_stops_when_a_large_payment_clears_it_early():
    s = lm.schedule(100_000, 12.0, 24, payment_cents=50_000)
    assert len(s) == 3
    assert s["closing"].iloc[-1] == 0


def test_effective_annual_rate():
    assert lm.effective_annual_rate(12.0) == pytest.approx(12.6825, abs=1e-4)
    assert lm.effective_annual_rate(12.0, periods=1) == pytest.approx(12.0)


def test_apr_without_fees_is_the_rate_in_each_convention():
    payments = lm.schedule(AMOUNT, RATE, TERM)["payment"].tolist()
    assert lm.apr(AMOUNT, payments, "nominal") == pytest.approx(RATE,
                                                                abs=1e-3)
    assert lm.apr(AMOUNT, payments) == pytest.approx(
        lm.effective_annual_rate(RATE), abs=1e-3)


def test_apr_rises_with_a_fee_and_rejects_unknown_conventions():
    payments = lm.schedule(AMOUNT, RATE, TERM)["payment"].tolist()
    assert lm.apr(AMOUNT - 50_000, payments) > lm.apr(AMOUNT, payments)
    with pytest.raises(ValueError):
        lm.apr(AMOUNT, payments, "flat")


def test_effective_interest_rate_moves_with_fees_and_costs():
    payments = lm.schedule(AMOUNT, RATE, TERM)["payment"].tolist()
    plain = lm.effective_interest_rate(AMOUNT, payments)
    assert plain == pytest.approx(RATE, abs=1e-3)
    assert lm.effective_interest_rate(
        AMOUNT, payments, costs_paid_cents=30_000) < plain
    assert lm.effective_interest_rate(
        AMOUNT, payments, fees_received_cents=30_000) > plain


def test_present_value_at_the_loan_rate_is_the_principal():
    payments = lm.schedule(AMOUNT, RATE, TERM)["payment"].tolist()
    # Rounding each month's interest to the cent moves it by cents.
    assert lm.present_value(payments, RATE) == pytest.approx(AMOUNT, abs=5)
    assert lm.present_value(payments, 3.0) > AMOUNT
    assert lm.present_value([100_000] * 1, 0.0) == 100_000


def test_revolve_at_the_minimum_uses_the_floor_and_clears():
    r = lm.revolve(165_540, 23.88)
    assert r["closing"].iloc[-1] == 0
    assert r["payment"].iloc[0] == round(
        (165_540 + round(165_540 * 23.88 / 1200)) * 0.025)
    assert (r["payment"].iloc[:-1] >= 2_500).all()


def test_revolve_with_a_fixed_payment_is_faster():
    at_min = lm.revolve(165_540, 23.88)
    fixed = lm.revolve(165_540, 23.88, payment_cents=10_000)
    assert len(fixed) < len(at_min)
    assert fixed["interest"].sum() < at_min["interest"].sum()


def test_revolve_never_clears_a_payment_below_the_interest():
    r = lm.revolve(1_000_000, 24.0, payment_cents=10_000, max_months=24)
    assert len(r) == 24
    assert r["closing"].iloc[-1] > 1_000_000


def test_loan_pnl_adds_up():
    p = lm.loan_pnl(AMOUNT, RATE, TERM, 3.0, annual_pd=0.02, lgd=0.8,
                    opex_pct=2.0)
    s = lm.schedule(AMOUNT, RATE, TERM)
    assert p["interest"] == s["interest"].sum()
    assert p["net"] == (p["interest"] - p["funding"] - p["opex"]
                        - p["expected_loss"])
    # Each cost is its rate on the sum of opening balances.
    owed = s["opening"].sum()
    assert p["funding"] == round(owed * 3.0 / 1200)
    assert p["expected_loss"] == round(owed * 0.02 / 12 * 0.8)


def test_loan_pnl_takes_a_cost_of_funds_per_month():
    flat = lm.loan_pnl(AMOUNT, RATE, TERM, 2.0)
    monthly = lm.loan_pnl(AMOUNT, RATE, TERM, [2.0] * TERM)
    assert flat == monthly
    assert lm.loan_pnl(AMOUNT, RATE, TERM, 0.0)["net"] == flat["interest"]


def test_break_even_default_rate():
    assert lm.break_even_default_rate(10.0, 3.0, 2.0, 0.5) == 10.0
    assert lm.break_even_default_rate(5.0, 3.0, 2.0, 0.8) == 0.0


@pytest.mark.skipif(not LOANBOOK.exists(), reason="no loan book")
def test_reproduces_every_booked_payment():
    import fernhill
    con = fernhill.connect()
    rows = con.execute("""
        SELECT product, amount_cents, rate_pct, term_months::INT,
               payment_cents::BIGINT
        FROM accounts WHERE payment_cents IS NOT NULL
    """).fetchall()
    assert len(rows) > 50_000
    # Emergency business loans: the first twelve months payment-free.
    wrong = [r for r in rows
             if lm.monthly_payment(*r[1:4], 12 if r[0] == "sme_emergency"
                                   else 0) != r[4]]
    assert wrong == []
