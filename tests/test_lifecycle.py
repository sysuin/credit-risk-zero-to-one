"""Tests for ballast.lifecycle: the step-to-table map and one loan's life."""
from __future__ import annotations

import datetime as dt

import pytest

import fernhill
from ballast.lifecycle import (STEPS, dollars, format_life, life,
                               month_spans)


@pytest.fixture(scope="module")
def con():
    return fernhill.connect()


def test_every_step_names_real_columns(con):
    for step in STEPS:
        have = {r[0] for r in con.execute(f"DESCRIBE {step.table}")
                .fetchall()}
        assert step.key in have, step
        assert set(step.columns) <= have, step


def test_steps_run_in_order_from_application_to_recovery():
    names = [s.name for s in STEPS]
    assert names[0] == "apply" and names[-1] == "recover"
    assert len(names) == len(set(names))


def test_a_loan_repaid_in_full(con):
    lf = life(con, "A00000004")
    assert [a["account_id"] for a in lf.accounts] == ["PL0000001"]
    acc = lf.accounts[0]
    assert acc["close_reason"] == "repaid"
    rows = lf.months["PL0000001"]
    assert len(rows) == 61
    assert rows[0]["month"] == dt.date(2016, 1, 31)
    assert not (lf.events or lf.collections or lf.defaults
                or lf.recoveries)


def test_spans_cover_every_month_and_every_payment(con):
    rows = life(con, "A00000004").months["PL0000001"]
    spans = month_spans(rows)
    assert sum(n for _, _, n, _, _ in spans) == len(rows)
    assert sum(p for *_, p in spans) == sum(r["paid_cents"]
                                            for r in rows)
    assert spans[0][3] == "opened, nothing due"


def test_a_car_taken_back(con):
    lf = life(con, "A00137123")
    acc = lf.accounts[0]
    assert acc["account_id"] == "AL0001201"
    assert acc["close_reason"] == "vehicle_repossessed"
    assert [c["action"] for c in lf.collections][-1] == "final_notice"
    assert len(lf.defaults) == 1
    kinds = {r["kind"] for r in lf.recoveries}
    assert {"collateral_sale", "collections_payment", "cost"} <= kinds


def test_a_declined_application_has_no_account(con):
    lf = life(con, "A00000001")
    assert lf.app["decision"] == "decline"
    assert lf.accounts == []
    assert format_life(lf)[-1] == "account     none"


def test_an_account_that_continued_under_a_new_number(con):
    app = con.execute("""SELECT app_id FROM accounts
                         WHERE predecessor_id IS NOT NULL
                         ORDER BY account_id LIMIT 1""").fetchone()[0]
    accounts = life(con, app).accounts
    assert len(accounts) == 2
    assert accounts[1]["predecessor_id"] == accounts[0]["account_id"]


def test_a_business_application(con):
    lf = life(con, "S0000001")
    assert lf.app["product"].startswith("sme_")
    assert lf.accounts and lf.months[lf.accounts[0]["account_id"]]


def test_unknown_application(con):
    with pytest.raises(KeyError):
        life(con, "A99999999")


def test_lines_fit_the_page(con):
    apps = [r[0] for r in con.execute("""
        SELECT app_id FROM applications
        WHERE app_id IN ('A00000004', 'A00137123')
           OR account_id IN (SELECT account_id FROM recoveries
                             WHERE kind = 'debt_sale' LIMIT 3)
        ORDER BY app_id""").fetchall()]
    assert len(apps) >= 3
    for app in apps:
        for line in format_life(life(con, app)):
            assert len(line) <= 68, line


def test_dollars():
    assert dollars(1510000) == "$15,100.00"
    assert dollars(-163974) == "-$1,639.74"
    assert dollars(None) == "-"
