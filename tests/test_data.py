"""Tests for ballast.data: the loaders type the loan book, and the checks
fail loudly when a rule is broken."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from ballast import data
from ballast.config import AS_OF


@pytest.fixture(scope="module")
def apps():
    return data.load_applications()


@pytest.fixture(scope="module")
def raw_apps():
    return data.load_applications(unknowns=False)


@pytest.fixture(scope="module")
def accounts():
    return data.load_accounts()


@pytest.fixture(scope="module")
def mortgages():
    return data.load_performance(products=["mortgage"])


def one_account(perf):
    first = perf["account_id"].iloc[0]
    out = perf[perf["account_id"] == first].reset_index(drop=True).copy()
    out.attrs = {}
    return out


# ------------------------------------------------------------- types

def test_applications_are_typed(apps):
    assert len(apps) == apps.attrs["source_rows"]
    assert str(apps["stated_income_cents"].dtype) == "Int64"
    assert str(apps["bureau_score"].dtype) == "Int64"
    assert str(apps["app_date"].dtype).startswith("date32")
    assert str(apps["income_verified"].dtype) == "boolean"
    assert isinstance(apps["product"].dtype, pd.CategoricalDtype)


def test_dates_compare_with_config_dates(apps):
    late = apps["app_date"] > AS_OF
    assert not late.any()
    v3 = apps["app_date"] >= data.BUREAU_V3_FROM
    assert set(apps.loc[v3 & apps["bureau_hit"], "bureau_version"]) == {"v3"}


def test_float_columns_become_whole_cents(accounts):
    assert str(accounts["payment_cents"].dtype) == "Int64"
    assert str(accounts["term_months"].dtype) == "Int64"


def test_performance_is_typed(mortgages):
    assert len(mortgages) == mortgages.attrs["source_rows"]
    assert str(mortgages["balance_cents"].dtype) == "Int64"
    assert str(mortgages["month"].dtype).startswith("date32")
    assert str(mortgages["payment_holiday"].dtype) == "boolean"


# ---------------------------------------------------------- unknowns

def test_no_hit_zeros_become_missing(apps, raw_apps):
    no_hit = ~apps["bureau_hit"]
    assert (raw_apps.loc[no_hit, "worst_status_24m"] == 0).all()
    assert apps.loc[no_hit, "worst_status_24m"].isna().all()
    assert apps.loc[~no_hit, "worst_status_24m"].notna().all()
    assert apps.attrs["unknowns"]["no_hit"] == 6 * int(no_hit.sum())


def test_consent_has_three_states(apps):
    offered = data.ob_offered(apps["channel"], apps["app_date"])
    assert apps.loc[~offered, "ob_consent"].isna().all()
    assert apps.loc[offered, "ob_consent"].notna().all()
    assert apps.loc[offered, "ob_consent"].any()
    assert not apps.loc[offered, "ob_consent"].all()


def test_card_requests_have_no_amount(apps):
    cards = apps["product"] == "card"
    assert apps.loc[cards, "amount_requested_cents"].isna().all()
    assert apps.loc[~cards, "amount_requested_cents"].notna().all()


def test_unknowns_can_be_left_alone(raw_apps):
    assert raw_apps.attrs["unknowns"] == {}
    assert raw_apps["worst_status_24m"].notna().all()


# ------------------------------------------------------------ checks

def test_the_loan_book_passes_every_check(apps, accounts, mortgages):
    data.check_links(apps, accounts, mortgages)


def test_repeated_application_fails(raw_apps):
    df = pd.concat([raw_apps.head(3), raw_apps.head(1)], ignore_index=True)
    with pytest.raises(data.DataCheckError, match="app_id missing or rep"):
        data.check_applications(df)


def test_wrong_bureau_version_fails(raw_apps):
    df = raw_apps.head(50).copy()
    df.attrs = {}
    hit = df.index[df["bureau_hit"]][0]
    df.loc[hit, "bureau_version"] = "v3"       # every row here is 2016
    with pytest.raises(data.DataCheckError, match="version does not"):
        data.check_applications(df)


def test_consent_before_it_was_offered_fails(raw_apps):
    df = raw_apps.head(50).copy()
    df.attrs = {}
    df.loc[0, "ob_consent"] = True
    with pytest.raises(data.DataCheckError, match="never offered"):
        data.check_applications(df)


def test_verified_income_without_the_flag_fails(raw_apps):
    df = raw_apps.head(50).copy()
    df.attrs = {}
    row = df.index[~df["income_verified"]][0]
    df.loc[row, "verified_income_cents"] = 4_000_000
    with pytest.raises(data.DataCheckError, match="verified income"):
        data.check_applications(df)


def test_a_short_load_fails(raw_apps):
    df = raw_apps.head(10).copy()
    df.attrs = {"source_rows": 11}
    with pytest.raises(data.DataCheckError, match="the source holds 11"):
        data.check_applications(df)


def test_repeated_account_month_fails(mortgages):
    df = one_account(mortgages)
    df = pd.concat([df, df.tail(1)], ignore_index=True)
    with pytest.raises(data.DataCheckError, match="account-month rep"):
        data.check_performance(df)


def test_negative_balance_fails(mortgages):
    df = one_account(mortgages)
    df.loc[2, "balance_cents"] = -1
    with pytest.raises(data.DataCheckError, match="balance_cents neg"):
        data.check_performance(df)


def test_missing_month_fails(mortgages):
    df = one_account(mortgages).drop(index=3)
    with pytest.raises(data.DataCheckError, match="a month missing"):
        data.check_performance(df)


def test_days_past_due_must_match_missed(mortgages):
    df = one_account(mortgages)
    df.loc[1, "days_past_due"] = 30
    with pytest.raises(data.DataCheckError, match="30 x missed"):
        data.check_performance(df)


def test_every_failure_is_reported_at_once(mortgages):
    df = one_account(mortgages)
    df.loc[1, "balance_cents"] = -5
    df.loc[2, "missed"] = -1
    with pytest.raises(data.DataCheckError) as err:
        data.check_performance(df)
    assert "failed 3 check(s)" in str(err.value)   # dpd no longer 30x


def test_unknown_category_fails():
    df = pd.DataFrame({"product": ["personal", "overdraft"]})
    with pytest.raises(data.DataCheckError, match="outside the known"):
        data._typed(df)


def test_fractional_cents_fail():
    df = pd.DataFrame({"payment_cents": [100.0, 100.5]})
    with pytest.raises(data.DataCheckError, match="not whole numbers"):
        data._typed(df)


def test_booked_application_without_account_fails(apps, accounts):
    booked = apps[apps["outcome"] == "booked"].head(5)
    missing = accounts[~accounts["account_id"].isin(
        [booked["account_id"].iloc[0]])]
    with pytest.raises(data.DataCheckError, match="with no account"):
        data.check_links(booked, missing)


def test_ob_offered_dates():
    ch = pd.Series(["online", "online", "branch", "branch", "broker"])
    when = pd.Series([dt.date(2021, 2, 28), dt.date(2021, 3, 1),
                      dt.date(2022, 12, 31), dt.date(2023, 1, 1),
                      dt.date(2025, 1, 1)])
    assert data.ob_offered(ch, when).tolist() == [
        False, True, False, True, False]
