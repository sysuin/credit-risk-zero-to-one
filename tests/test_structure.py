"""Tests for ballast.commercial.structure: sizing, the borrowing base,
covenants and their headroom, distributions, income and the term
sheet."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def toy_spread() -> pd.DataFrame:
    """Two years of a small consistent company (as in
    test_spreading), spread. 2025: receivables 130, inventory 100,
    payables 80, borrowings 100 (30 due in a year), EBITDA 150,
    interest 10, all in dollars."""
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
                current_liabilities=[100_00, 110_00],
                payables=[70_00, 80_00], dividends=[10_00, 25_00],
                total_debt=[100_00, 100_00],
                equity=[260_00, 300_00], capex=[30_00, 35_00],
                operating_cash_flow=[50_00, 50_00])
    df = pd.DataFrame({k: v if isinstance(v, list) else [v, v]
                       for k, v in base.items()})
    df["fiscal_year"] = [2024, 2025]
    return sp.spread(df)


# ------------------------------------------------------------ sizing

def test_working_capital_and_need():
    s = toy_spread()
    assert st.working_capital(s, 2025) == 150_00
    need = st.revolver_need(s, 2025, growth=0.10, years=2, swing=0.10)
    # 150 grows to 181.50: 31.50 of growth, 18.15 of swing, 30 refi
    assert need["refinance"] == 30_00
    assert need["growth"] == 31_50
    assert need["swing"] == 18_15
    assert need["total"] == 79_65
    assert need["limit"] == 100_000_000      # rounded up to $1m


def test_need_can_refinance_something_else():
    need = st.revolver_need(toy_spread(), 2025, growth=0.0,
                            refinance=0, swing=0.0)
    assert need["total"] == 0 and need["limit"] == 0


def test_pro_forma_charges_old_and_new_debt_differently():
    pf = st.pro_forma(toy_spread(), 2025, add=50_00, keep=70_00,
                      rate_new=0.08)
    # kept 70 at the implied 10%, new 50 at 8%: interest 11
    assert pf.debt == 120_00
    assert pf.interest == pytest.approx(11_00)
    assert pf.leverage == pytest.approx(0.8)
    assert pf.cover == pytest.approx(150 / 11)


# -------------------------------------------------- borrowing base

def test_borrowing_base_arithmetic():
    bb = st.borrowing_base(1_000_00, 400_00,
                           ineligible_receivables=150_00,
                           ineligible_inventory=100_00,
                           advance_receivables=0.8,
                           advance_inventory=0.5, reserves=20_00)
    assert bb.eligible_receivables == 850_00
    assert bb.receivables_advance == 680_00
    assert bb.eligible_inventory == 300_00
    assert bb.inventory_advance == 150_00
    assert bb.base == 680_00 + 150_00 - 20_00
    assert bb.ineligible_receivables == -150_00


def test_borrowing_base_defaults_and_rounding_down():
    bb = st.borrowing_base(101, 0)
    inel = round(101 * st.INELIGIBLE_RECEIVABLES)
    assert bb.ineligible_receivables == -inel
    assert bb.receivables_advance == math.floor(
        (101 - inel) * st.ADVANCE_RECEIVABLES)


def test_borrowing_base_never_negative():
    assert st.borrowing_base(100_00, 0, reserves=1_000_00).base == 0


def test_availability_is_lesser_of_limit_and_base_less_drawn():
    assert st.availability(base=80, limit=100, drawn=30) == 50
    assert st.availability(base=150, limit=100, drawn=30) == 70
    assert st.availability(base=20, limit=100, drawn=30) == 0


def test_ineligible_receivables_rules():
    ledger = pd.DataFrame({
        "customer": ["A", "B", "C", "D", "E"],
        "balance": [100_00, 50_00, 40_00, 400_00, 10_00],
        "over_days": [10_00, 30_00, 0, 0, 0],
        "flag": [None, None, "disputed", None, None],
    })
    d = st.ineligible_receivables(ledger, cross_age=0.5,
                                  concentration=0.25)
    out = dict(zip(d.customer, d.ineligible))
    assert out["A"] == 10_00          # the overdue part only
    assert out["B"] == 50_00          # cross-aged: 60% overdue
    assert out["C"] == 40_00          # disputed
    # total 600: one customer may carry 150; D's 400 leaves 250 out
    assert out["D"] == 250_00
    assert out["E"] == 0
    assert dict(zip(d.customer, d.reason))["D"] == "concentration"
    assert (d.eligible + d.ineligible == d.balance).all()


# --------------------------------------------------------- covenants

def test_covenant_levels_have_the_headroom_rounded():
    # 2.30 / 0.7 = 3.29 -> 3.25; 6.26 x 0.7 = 4.38 -> 4.50
    assert st.covenant_levels(2.30, 6.26) == (3.25, 4.5)
    assert st.covenant_levels(2.0, 10.0, headroom=0.5) == (4.0, 5.0)


def test_breaches_handle_losses_and_no_interest():
    b = st.breaches([100, 100, 100, 100], [50, 20, -5, 50],
                    [10, 10, 10, 0], 3.0, 3.0)
    assert list(b.leverage_breach) == [False, True, True, False]
    assert list(b.cover_breach) == [False, True, True, False]
    assert np.isinf(b.leverage[2]) and np.isinf(b.cover[3])
    assert list(b.breach) == [False, True, True, False]


def test_ebitda_headroom_by_hand():
    lev, cov = st.ebitda_headroom(2.0, 8.0, 3.0, 4.0)
    assert lev == pytest.approx(1 / 3)
    assert cov == pytest.approx(0.5)
    # a leverage of 2 under a cap of 3 breaks when EBITDA is 2/3
    assert 2.0 / (1 - lev) == pytest.approx(3.0)


def test_covenant_test_on_a_spread():
    t = st.covenant_test(toy_spread(), max_leverage=1.0,
                         min_cover=12.5)
    assert t.loc["leverage", 2025] == pytest.approx(100 / 150)
    assert t.loc["cover", 2024] == pytest.approx(12.0)
    assert t.loc["cover_breach", 2024] and t.loc["breach", 2024]
    assert not t.loc["breach", 2025]
    assert t.loc["cover_headroom", 2025] == pytest.approx(1 - 12.5 / 15)


def test_permitted_distribution():
    assert st.permitted_distribution(1_000_00, 1.5, payout_cap=0.35,
                                     max_leverage=2.5) == 350_00
    assert st.permitted_distribution(1_000_00, 2.6,
                                     max_leverage=2.5) == 0
    assert st.permitted_distribution(-5_00, 1.0) == 0
    assert st.permitted_distribution(1_000_00, 1.0,
                                     in_default=True) == 0


# ---------------------------------------------- income and the terms

def test_facility_income():
    inc = st.facility_income(limit=1_000_000_00, drawn=600_000_00,
                             margin_bps=250, tenor_years=4,
                             commitment_share=0.4,
                             arrangement_pct=0.01)
    assert inc.margin == 15_000_00
    assert inc.commitment_fee == 4_000_00      # 400k x 2.5% x 0.4
    assert inc.arrangement_fee == 2_500_00     # 10k over 4 years
    assert inc.total == 21_500_00


def test_term_sheet_fits_the_page():
    ts = st.TermSheet(borrower="T1", limit_cents=10_000_000_00,
                      tenor_months=36, purpose="Working capital.",
                      margin_bps=275, reference="Reference rate",
                      max_leverage=3.25, min_cover=4.5,
                      security="First-ranking security over "
                               "receivables and inventory." * 3,
                      reporting=["monthly certificate"],
                      conditions=["audited accounts"])
    lines = st.format_term_sheet(ts)
    assert all(len(x) <= 68 for x in lines)
    text = "\n".join(lines)
    assert "$10,000,000" in text and "3.25x" in text
    assert "96 bps" in text          # 35% of 275
    assert "Guarantees" not in text  # empty rows are left out


# ------------------------------------------------------ the loan book

@needs_book
def test_meridian_structure():
    con = fernhill.connect()
    m = sp.company_id(con, "Meridian Supply Co.")
    s = sp.spread(sp.accounts(con, m))
    need = st.revolver_need(s, 2025, growth=0.137)
    assert need.refinance == s.loc["short_term_debt", 2025]
    assert 10_000_000_00 < need.limit <= 20_000_000_00
    bb = st.borrowing_base(s.loc["receivables", 2025],
                           s.loc["inventory", 2025])
    assert bb.base > need.limit         # not binding on day one
    pf = st.pro_forma(s, 2025, add=int(need.limit),
                      keep=int(s.loc["long_term_debt", 2025]),
                      rate_new=0.065)
    cap, floor = st.covenant_levels(pf.leverage, pf.cover)
    t = st.covenant_test(s, cap, floor)
    assert not t.loc["breach"].any()    # history passes


@needs_book
def test_fernhill_facilities_are_all_senior():
    con = fernhill.connect()
    rows = con.execute("""SELECT seniority, count(*) FROM facilities
                          GROUP BY 1""").fetchall()
    assert rows == [("senior", 897)]
