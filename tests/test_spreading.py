"""Tests for ballast.commercial.spreading: the derived lines, the
checks, the ratios, the cash bridge and the peer comparison."""
from __future__ import annotations

import math

import pandas as pd
import pytest

import fernhill
from ballast.commercial import spreading as sp
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def toy(**change) -> pd.DataFrame:
    """Two years of a small, internally consistent company, in cents.

    Year two: revenue 1,000, receivables up 30, inventory up 20,
    payables up 10, so operating cash flow (after interest and tax)
    is net income 65 + depreciation 25 - 30 - 20 + 10 = 50.
    Dividends of 25 and capex of 35 take cash from 50 to 40.
    """
    base = dict(company_id="T1", basis="audited",
                revenue=[800_00, 1_000_00], cogs=[560_00, 700_00],
                opex=[120_00, 150_00], ebitda=[120_00, 150_00],
                depreciation=[20_00, 25_00], ebit=[100_00, 125_00],
                interest=[10_00, 10_00], tax=[40_00, 50_00],
                net_income=[50_00, 65_00], cash=[50_00, 40_00],
                receivables=[100_00, 130_00],
                inventory=[80_00, 100_00],
                current_assets=[230_00, 270_00],
                total_assets=[430_00, 480_00],
                # current liabilities = 30 short-term debt + payables
                # + 0 accruals
                current_liabilities=[100_00, 110_00],
                payables=[70_00, 80_00], dividends=[10_00, 25_00],
                total_debt=[100_00, 100_00],
                equity=[260_00, 300_00], capex=[30_00, 35_00],
                operating_cash_flow=[50_00, 50_00])
    base.update(change)
    df = pd.DataFrame({k: v if isinstance(v, list) else [v, v]
                       for k, v in base.items()})
    df["fiscal_year"] = [2024, 2025]
    return df


# ------------------------------------------------------ derived lines

def test_derived_lines_split_borrowings():
    s = sp.spread(toy())
    # liabilities 180 = current 110 + long-term 70; borrowings 100
    assert s.loc["total_liabilities", 2025] == 180_00
    assert s.loc["long_term_debt", 2025] == 70_00
    assert s.loc["short_term_debt", 2025] == 30_00
    assert s.loc["payables", 2025] == 80_00
    assert s.loc["accruals", 2025] == 0
    assert s.loc["other_long_term", 2025] == 0
    assert s.loc["gross_profit", 2025] == 300_00
    assert s.loc["pre_tax", 2025] == 115_00
    # operating cash flow is after interest, so only capex comes off
    assert s.loc["free_cash_flow", 2025] == 50_00 - 35_00


def test_balance_sheet_balances_after_derivation():
    s = sp.spread(toy())
    left = s.loc["total_assets"]
    right = (s.loc["current_liabilities"] + s.loc["long_term_debt"]
             + s.loc["other_long_term"] + s.loc["equity"])
    assert (left == right).all()


def test_long_term_items_beyond_borrowings_are_kept_apart():
    # equity 60 lower: long-term liabilities of 130 exceed the 100
    # of borrowings, so 30 are something else
    s = sp.spread(toy(equity=[200_00, 240_00]))
    assert s.loc["long_term_debt", 2025] == 100_00
    assert s.loc["other_long_term", 2025] == 30_00
    assert s.loc["short_term_debt", 2025] == 0
    assert s.loc["accruals", 2025] == 30_00
    assert any("long-term" in p for p in sp.problems(s))


def test_spread_refuses_two_companies():
    df = toy()
    df.loc[1, "company_id"] = "T2"
    with pytest.raises(ValueError):
        sp.spread(df)


def test_format_spread_fits_the_page():
    lines = sp.format_spread(sp.spread(toy()))
    assert max(len(x) for x in lines) <= 68
    assert "unaudited" not in lines[1]


# ------------------------------------------------------------ checks

def test_consistent_accounts_have_no_problems():
    assert sp.problems(sp.spread(toy())) == []
    # a total one cent off its parts is rounding, not an error
    s = sp.spread(toy(ebitda=[120_00, 150_01], ebit=[100_00, 125_01],
                      net_income=[50_00, 65_00]))
    assert sp.problems(s) == []


def test_problems_find_broken_arithmetic_and_negative_equity():
    s = sp.spread(toy(net_income=[50_00, 64_00]))
    assert sp.problems(s) == [
        "2025: net income is EBIT less interest and tax"]
    s = sp.spread(toy(equity=[-1_00, -1_00]))
    assert any("equity is positive" in p for p in sp.problems(s))


def test_roll_forward_closes_on_consistent_accounts():
    roll = sp.roll_forward(sp.spread(toy()))
    assert list(roll.columns) == [2025]
    # equity +40 = profit 65 - dividends 25
    assert roll.loc["dividends", 2025] == -25_00
    assert roll.loc["equity_other", 2025] == 0
    # fixed assets +10 = capex 35 - depreciation 25
    assert roll.loc["fixed_other", 2025] == 0
    # cash -10 = FCF 15 + no new debt - 25 paid out
    assert roll.loc["cash_other", 2025] == 0
    # a dividend the equity line does not show is caught
    roll = sp.roll_forward(sp.spread(toy(dividends=[10_00, 5_00])))
    assert roll.loc["equity_other", 2025] == -20_00


# ------------------------------------------------------------ ratios

def test_ratios_by_hand():
    r = sp.ratios(sp.spread(toy()))[2025]
    assert r.revenue_growth == pytest.approx(0.25)
    assert r.ebitda_margin == pytest.approx(0.15)
    assert r.leverage == pytest.approx(100 / 150)
    assert r.net_leverage == pytest.approx(60 / 150)
    assert r.interest_cover == pytest.approx(15.0)
    assert r.current_ratio == pytest.approx(270 / 110)
    assert r.quick_ratio == pytest.approx(170 / 110)
    assert r.receivable_days == pytest.approx(365 * 130 / 1000)
    assert r.inventory_days == pytest.approx(365 * 100 / 700)
    assert r.payable_days == pytest.approx(365 * 80 / 700)
    assert r.payout == pytest.approx(25 / 65)
    assert r.cash_cycle == pytest.approx(
        r.receivable_days + r.inventory_days - r.payable_days)
    assert r.cash_conversion == pytest.approx(50 / 150)


def test_dscr_assumptions():
    d = sp.spread(toy()).T
    # EBITDA basis: (150 - 50 - 35) / (10 + 100 / 5)
    v = sp.dscr(d, d.total_debt / 5)
    assert v[2025] == pytest.approx(65 / 30)
    # cash basis: (50 - 35 + interest 10) / (10 + 30 due in a year)
    v = sp.dscr(d, d.short_term_debt, basis="cash")
    assert v[2025] == pytest.approx(25 / 40)
    r = sp.ratios(sp.spread(toy()), amortisation_years=10)
    assert r.loc["dscr", 2025] == pytest.approx(65 / 20)
    with pytest.raises(ValueError):
        sp.dscr(d, 0, basis="profit")


def test_ratio_with_zero_denominator_is_missing():
    r = sp.ratios(sp.spread(toy(interest=[0, 0],
                                net_income=[60_00, 75_00])))
    assert math.isnan(r.loc["interest_cover", 2025])


def test_cash_bridge_closes_on_consistent_accounts():
    b = sp.cash_bridge(sp.spread(toy()))
    assert b.loc["interest", 2025] == -10_00
    assert b.loc["derived", 2025] == 50_00
    assert b.loc["unexplained", 2025] == 0


def test_compare_counts_ties_as_half():
    peers = pd.DataFrame({"leverage": [1.0, 2.0, 2.0, 3.0]})
    c = sp.compare(pd.Series({"leverage": 2.0}), peers)
    assert c.loc["leverage", "share_below"] == pytest.approx(0.5)
    assert c.loc["leverage", "median"] == pytest.approx(2.0)
    assert c.loc["leverage", "n"] == 4


# ---------------------------------------------------- the loan book

@needs_book
def test_meridian_matches_the_earlier_books():
    con = fernhill.connect()
    s = sp.spread(sp.accounts(con, "C0266"))
    assert list(s.columns) == [2022, 2023, 2024, 2025]
    assert s.loc["revenue"].tolist() == [
        6_126_203_600, 10_142_361_900, 11_198_454_300, 12_734_834_600]
    assert s.loc["cogs", 2022] == 4_325_720_000
    assert s.attrs["basis"][2025] == "management"
    assert sp.problems(s) == []
    roll = sp.roll_forward(s)
    for line in ("equity_other", "fixed_other", "cash_other"):
        assert (roll.loc[line] == 0).all()
    assert (sp.cash_bridge(s).loc["unexplained"] == 0).all()


@needs_book
def test_meridian_story_holds():
    con = fernhill.connect()
    r = sp.ratios(sp.spread(sp.accounts(con, "C0266")))
    days = r.loc["receivable_days"].round().tolist()
    assert days == [48, 52, 58, 66]
    assert r.loc["payable_days"].round().tolist() == [46, 45, 44, 43]
    assert r.loc["payout", 2025] > 0.5
    assert r.loc["leverage", 2025] < 2


@needs_book
def test_peers_exclude_the_prospect_and_have_one_year():
    con = fernhill.connect()
    acc = sp.peer_accounts(con, "wholesale", 2024, exclude=["C0266"])
    assert "C0266" not in acc.index
    assert len(acc) == 23
    assert (acc.fiscal_year == 2024).all()
    # every peer's long-term liabilities fit inside its borrowings
    assert (acc.other_long_term == 0).all()
    with pytest.raises(KeyError):
        sp.accounts(con, "C9999")
