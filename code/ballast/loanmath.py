"""Ballast v0.1: the arithmetic of a loan.

Payments, schedules, rates and a simple loan P&L, in the units of
Fernhill's own tables: money in integer cents, rates as annual
percentages (10.9 means 10.9% a year), terms in months.

Every interest calculation here is monthly: a month's interest is the
balance times the annual rate divided by twelve, rounded to the cent.
That is how Fernhill's instalment loans are booked.
"""
from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from scipy.optimize import brentq


def monthly_rate(rate_pct: float) -> float:
    """The rate charged each month on a nominal annual rate."""
    return rate_pct / 100 / 12


def monthly_payment(principal_cents: int, rate_pct: float,
                    term_months: int, free_months: int = 0) -> int:
    """The level monthly payment that repays a loan, in cents.

    If the first `free_months` are payment-free, interest is added to
    the balance in them and the payment repays what the balance has
    grown to over the months that remain.
    """
    r = monthly_rate(rate_pct)
    owed = principal_cents * (1 + r) ** free_months
    months = term_months - free_months
    if r == 0:
        return round(owed / months)
    return round(owed * r / (1 - (1 + r) ** -months))


def schedule(principal_cents: int, rate_pct: float, term_months: int,
             payment_cents: int | None = None,
             free_months: int = 0) -> pd.DataFrame:
    """The amortisation schedule: one row per month, all in cents.

    Each month the balance earns a month's interest and the payment
    pays that interest first and the principal with what is left.
    The last payment is whatever clears the balance, which differs
    from the others by the rounding of the level payment. In any
    payment-free months at the start, the interest is added to the
    balance instead (the principal column is negative).
    """
    if payment_cents is None:
        payment_cents = monthly_payment(principal_cents, rate_pct,
                                        term_months, free_months)
    r = monthly_rate(rate_pct)
    rows = []
    balance = principal_cents
    for month in range(1, term_months + 1):
        interest = round(balance * r)
        payment = payment_cents if month > free_months else 0
        if month == term_months or payment > balance + interest:
            payment = balance + interest
        principal = payment - interest
        rows.append((month, balance, interest, principal, payment,
                     balance - principal))
        balance -= principal
        if balance == 0:
            break
    return pd.DataFrame(rows, columns=["month", "opening", "interest",
                                       "principal", "payment",
                                       "closing"])


def effective_annual_rate(rate_pct: float, periods: int = 12) -> float:
    """What a nominal rate charged `periods` times a year comes to
    over a whole year, as a percentage."""
    return ((1 + rate_pct / 100 / periods) ** periods - 1) * 100


def implied_monthly_rate(amount_cents: float,
                         payments_cents: Sequence[float]) -> float:
    """The monthly rate at which the payments are worth exactly the
    amount: payment t (t = 1, 2, ...) is discounted t months.

    There is no formula for it, so it is found numerically: brentq
    narrows an interval in which the gap changes sign until the gap
    is zero to within a tiny tolerance.
    """
    def gap(r: float) -> float:
        return present_value_monthly(payments_cents, r) - amount_cents

    return brentq(gap, -0.5, 1.0, xtol=1e-14, maxiter=200)


def apr(amount_received_cents: float, payments_cents: Sequence[float],
        convention: str = "effective") -> float:
    """The annual percentage rate on what the borrower received.

    `effective` compounds the monthly rate over twelve months;
    `nominal` multiplies it by twelve. Jurisdictions differ on which
    one the paperwork must show (see Chapter 2).
    """
    m = implied_monthly_rate(amount_received_cents, payments_cents)
    if convention == "effective":
        return ((1 + m) ** 12 - 1) * 100
    if convention == "nominal":
        return m * 12 * 100
    raise ValueError(f"unknown convention {convention!r}")


def effective_interest_rate(principal_cents: int,
                            payments_cents: Sequence[float],
                            fees_received_cents: int = 0,
                            costs_paid_cents: int = 0) -> float:
    """The lender's effective interest rate, in the convention of
    `rate_pct` (twelve times the monthly rate).

    It is the rate that discounts the contractual payments to what
    the loan cost the lender on the day it was made: the principal,
    less fees the borrower paid the lender, plus costs the lender
    paid to originate it, such as a broker's commission. With no fees
    and no costs it is the contract rate.
    """
    carrying = principal_cents - fees_received_cents + costs_paid_cents
    return implied_monthly_rate(carrying, payments_cents) * 12 * 100


def present_value_monthly(cashflows_cents: Sequence[float],
                          monthly_r: float) -> float:
    """Cash flows one, two, three ... months away, discounted at a
    monthly rate, in cents (not rounded)."""
    return sum(cf / (1 + monthly_r) ** t
               for t, cf in enumerate(cashflows_cents, start=1))


def present_value(cashflows_cents: Sequence[float],
                  rate_pct: float) -> float:
    """Monthly cash flows discounted at a nominal annual rate."""
    return present_value_monthly(cashflows_cents,
                                 monthly_rate(rate_pct))


def revolve(balance_cents: int, rate_pct: float, *,
            minimum_pct: float = 2.5, minimum_floor_cents: int = 2500,
            payment_cents: int | None = None,
            max_months: int = 1200) -> pd.DataFrame:
    """A card balance with no new spending, month by month, in cents.

    Each month the balance is charged a month's interest; then the
    cardholder pays either `payment_cents` (if given) or the minimum:
    the greater of `minimum_pct` of the new balance and the floor,
    or the whole balance if that is smaller. Fernhill's minimum is
    2.5% or $25.
    """
    r = monthly_rate(rate_pct)
    rows = []
    balance = balance_cents
    for month in range(1, max_months + 1):
        interest = round(balance * r)
        owed = balance + interest
        if payment_cents is None:
            due = max(round(owed * minimum_pct / 100),
                      minimum_floor_cents)
        else:
            due = payment_cents
        payment = min(due, owed)
        rows.append((month, balance, interest, payment, owed - payment))
        balance = owed - payment
        if balance == 0:
            break
    return pd.DataFrame(rows, columns=["month", "opening", "interest",
                                       "payment", "closing"])


def loan_pnl(principal_cents: int, rate_pct: float, term_months: int,
             cost_of_funds_pct: float | Sequence[float], *,
             annual_pd: float = 0.0, lgd: float = 0.0,
             opex_pct: float = 0.0) -> dict[str, int]:
    """A simple profit and loss for one loan over its scheduled life.

    Each month, on the balance outstanding at its start, the lender
    earns the scheduled interest and pays: its cost of funds (a
    single annual rate, or one per month), its operating cost (a
    percentage of the balance a year) and an expected credit loss
    (the balance times the annual probability of default over twelve
    times the loss given default). Everything is in cents.

    It is deliberately simple: it assumes the loan runs to term, and
    does not shrink the balance for the loans that default or repay
    early. Chapter 12 prices properly.
    """
    sched = schedule(principal_cents, rate_pct, term_months)
    if isinstance(cost_of_funds_pct, (int, float)):
        cof = [float(cost_of_funds_pct)] * len(sched)
    else:
        cof = list(cost_of_funds_pct)[:len(sched)]
    opening = sched["opening"].tolist()
    funding = sum(b * c / 1200 for b, c in zip(opening, cof))
    opex = sum(b * opex_pct / 1200 for b in opening)
    loss = sum(b * annual_pd / 12 * lgd for b in opening)
    interest = int(sched["interest"].sum())
    out = {"interest": interest, "funding": round(funding),
           "opex": round(opex), "expected_loss": round(loss)}
    out["net"] = (out["interest"] - out["funding"] - out["opex"]
                  - out["expected_loss"])
    return out


def break_even_default_rate(rate_pct: float, cost_of_funds_pct: float,
                            opex_pct: float, lgd: float) -> float:
    """The annual default rate, in percent, at which a loan's margin
    after funding and operating costs is used up by credit losses.

    Per dollar of balance for a year: the margin is the rate less the
    cost of funds and the operating cost; each default loses `lgd` of
    the balance. A simplification: it ignores the interest a default
    stops paying and the time it takes to recover anything.
    """
    margin = rate_pct - cost_of_funds_pct - opex_pct
    return margin / lgd
