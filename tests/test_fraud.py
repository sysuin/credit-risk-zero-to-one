"""Tests for ballast.fraud: the first-payment markers, the rules, and
what each rule costs."""
from __future__ import annotations

import datetime as dt
import inspect

import numpy as np
import pandas as pd
import pytest

from ballast import fraud
from ballast.config import LOANBOOK


def _apps():
    """Four applications, each built to raise particular flags."""
    return pd.DataFrame({
        "app_date": [dt.date(2024, 5, 1)] * 4,
        "channel": ["online", "online", "broker", "branch"],
        "age": [45, 22, 45, 60],
        "bureau_hit": [True, True, True, False],
        "oldest_account_months": [12, 12, 200, 0],
        "address_months": [3, 40, 40, 100],
        "enquiries_6m": [5, 0, 1, 0],
        "stated_income_cents": [6_000_000, 3_210_000, 5_000_000,
                                4_150_000],
        "income_verified": [True, False, True, False],
        "verified_income_cents": pd.array([3_000_000, None, 4_900_000,
                                           None], dtype="Int64"),
        "ob_consent": [False, True, False, False],
    })


def test_each_rule_fires_where_it_should():
    f = fraud.flags(_apps(), rules=list(fraud.RULES))
    assert f.loc[0].all()                     # every flag at once
    assert f.loc[1, "young_file"]             # a young file at 22 ...
    assert not f.loc[1, "file_younger_than_person"]   # ... is normal
    assert list(f.columns[f.loc[2]]) == ["round_income"]
    # No file: the file rules cannot fire; a branch applicant in 2024
    # was asked for consent, and said no.
    assert list(f.columns[f.loc[3]]) == ["refused_consent"]


def test_never_asked_is_not_a_refusal():
    a = _apps()
    a["channel"] = "broker"                   # brokers never ask
    assert not fraud.refused_consent(a).any()


def test_income_ratio_only_where_verified():
    r = fraud.income_ratio(_apps())
    assert r.iloc[0] == pytest.approx(0.5)
    assert r.iloc[2] == pytest.approx(0.98)
    assert r.iloc[[1, 3]].isna().all()


def test_missing_values_do_not_fire():
    a = _apps()
    a["address_months"] = pd.array([None] * 4, dtype="Int64")
    assert not fraud.flags(a, ["new_address"])["new_address"].any()


def test_referral_threshold():
    f = fraud.flags(_apps())
    n = f.sum(axis=1)
    assert fraud.referred(f).equals((n >= fraud.REFER_AT)
                                    .rename("referred"))
    assert fraud.referred(f).tolist() == [True, False, False, False]


def test_rule_table_counts_and_costs():
    f = pd.DataFrame({"a": [True, True, True, False, False],
                      "b": [False, False, False, False, True]})
    marked = [True, False, False, True, False]
    t = fraud.rule_table(f, marked)
    assert t.loc["a", "flagged"] == 3 and t.loc["a", "caught"] == 1
    assert t.loc["a", "share_caught"] == pytest.approx(0.5)
    assert t.loc["a", "precision"] == pytest.approx(1 / 3)
    assert t.loc["a", "false_per_catch"] == pytest.approx(2.0)
    assert t.loc["b", "caught"] == 0
    assert np.isinf(t.loc["b", "false_per_catch"])


def test_fraud_never_reads_the_truth():
    assert "truth" not in inspect.getsource(fraud).replace(
        "truth database", "")


@pytest.mark.skipif(not LOANBOOK.exists(), reason="needs the loan book")
def test_first_payment_markers_on_the_loan_book():
    fp = fraud.first_payments()
    assert fp["account_id"].is_unique
    assert fp["account_id"].str.startswith("PL").all()
    # Never paid implies the first payment was missed.
    known = fp["never_paid"].notna()
    never = fp.loc[known, "never_paid"].astype(bool)
    assert fp.loc[known & never.reindex(fp.index, fill_value=False),
                  "first_missed"].all()
    # Accounts with fewer than three payments due have no marker yet.
    assert fp.loc[fp["due_seen"] < 3, "never_paid"].isna().all()
