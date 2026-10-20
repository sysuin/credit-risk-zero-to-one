"""Tests for ballast.commercial.memo: the figures table, the text
layout and the Markdown version."""
from __future__ import annotations

import pandas as pd
import pytest

import fernhill
from ballast.commercial import memo as mm
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st
from ballast.config import LOANBOOK

needs_book = pytest.mark.skipif(not LOANBOOK.exists(),
                                reason="no loan book")


def terms() -> st.TermSheet:
    return st.TermSheet(borrower="T1", limit_cents=10_000_000_00,
                        tenor_months=36, purpose="Working capital.",
                        margin_bps=275, reference="Reference rate",
                        max_leverage=3.25, min_cover=4.0,
                        security="First-ranking over receivables.",
                        conditions=["audited accounts"])


def toy_memo(**change) -> mm.Memo:
    base = dict(
        borrower="T1 Ltd", request="R1, $12m revolver",
        prepared="5 January 2026", decision="approve",
        recommendation="Approve a smaller facility. " * 12,
        terms=terms(),
        figures=[("Revenue, $m", ["1.0", "2.0"]),
                 ("Debt / EBITDA", ["1.50x", ""])],
        figure_years=["2025", "PF"],
        case_for=["Profitable every year, and a long sentence that "
                  "must wrap onto a second line of the memo."],
        risks=[("Receivables are slow.", "A borrowing base.")],
        conditions=["Audited accounts."],
        questions=["Why?"], rating="To follow.")
    base.update(change)
    return mm.Memo(**base)


def test_render_fits_68_characters_and_has_every_section():
    lines = mm.render(toy_memo())
    assert all(len(x) <= 68 for x in lines)
    assert all(x == x.rstrip() for x in lines)
    text = "\n".join(lines)
    for heading in ["RECOMMENDATION", "FACILITY PROPOSED", "FIGURES",
                    "THE CASE FOR LENDING", "RISKS",
                    "CONDITIONS BEFORE FIRST DRAWING",
                    "STILL TO BE ANSWERED", "RATING"]:
        assert heading in text
    assert "DECISION   APPROVE".lower() in text.lower()
    assert "$10,000,000" in text and "3.25x" in text
    assert "96 bps undrawn" in text


def test_empty_optional_sections_are_left_out():
    text = "\n".join(mm.render(toy_memo(questions=[], rating="")))
    assert "STILL TO BE ANSWERED" not in text
    assert "RATING" not in text


def test_markdown_has_tables():
    md = mm.to_markdown(toy_memo())
    assert md.startswith("# Credit memorandum: T1 Ltd")
    assert "| Limit | $10,000,000 |" in md
    assert "| | 2025 | PF |" in md
    assert "1. Audited accounts." in md


def test_key_figures_come_from_the_spread_and_ratios():
    s = pd.DataFrame({2024: {"revenue": 100_000_000,
                             "ebitda": 10_000_000,
                             "total_debt": 20_000_000,
                             "free_cash_flow": -5_000_000},
                      2025: {"revenue": 150_000_000,
                             "ebitda": 12_000_000,
                             "total_debt": 24_000_000,
                             "free_cash_flow": 1_000_000}})
    r = pd.DataFrame({2024: {"leverage": 2.0, "interest_cover": 5.0,
                             "receivable_days": 40.4, "payout": 0.2},
                      2025: {"leverage": 2.0, "interest_cover": 6.0,
                             "receivable_days": 50.6, "payout": 0.5}})
    years, rows = mm.key_figures(s, r, extra={"PF": {"leverage": 3.0}})
    assert years == ["2024", "2025", "PF"]
    got = dict(rows)
    assert got["Revenue, $m"] == ["1.0", "1.5", ""]
    assert got["Debt / EBITDA"] == ["2.00x", "2.00x", "3.00x"]
    assert got["Receivable days"] == ["40", "51", ""]
    assert got["Dividends / net income"] == ["20%", "50%", ""]
    assert got["Free cash flow, $m"] == ["-0.1", "0.0", ""]


@needs_book
def test_meridian_memo_quotes_the_spread():
    con = fernhill.connect()
    m = sp.company_id(con, "Meridian Supply Co.")
    s = sp.spread(sp.accounts(con, m))
    years, rows = mm.key_figures(s, sp.ratios(s))
    got = dict(rows)
    assert years == ["2022", "2023", "2024", "2025"]
    assert got["Revenue, $m"][-1] == "127.3"
    assert got["Receivable days"] == ["48", "52", "58", "66"]
    assert got["Dividends / net income"][-1] == "57%"
