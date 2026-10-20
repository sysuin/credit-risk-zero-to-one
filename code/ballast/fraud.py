"""Fraud: the first-payment signature, application rules, and what
income verification finds.

A lender rarely learns for certain that a loan was a fraud. What it
sees is the payment record, and a loan taken out by someone who never
meant to repay has a signature there: the first payment is missed, and
so is every one after it. This module measures it two ways for each
account, from the first month with a payment due:

- **first payment missed**: the first instalment was not paid;
- **never paid**: the first three instalments were all missed, so the
  account reached 90 days past due without a single payment.

The second is the stricter marker, and the one the rules are measured
against: a borrower in ordinary difficulty who misses the first payment
usually pays something within three months.

The rules read only the application, as Fernhill's fraud checks would
before a decision. Each is a red flag investigators recognise, written
as data; an application that raises `REFER_AT` or more is referred to
the fraud team, never declined by a rule alone.

    from ballast import fraud
    fp = fraud.first_payments(con)             # one row per account
    f = fraud.flags(apps)                      # one column per rule
    fraud.referred(f)                          # REFER_AT or more
    fraud.rule_table(f, marker)                # what each rule costs
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

import fernhill
from ballast.data import ob_offered

FIRST_DUE_SQL = """
WITH due AS (
    SELECT p.account_id, p.missed,
           row_number() OVER (PARTITION BY p.account_id
                              ORDER BY p.month) AS k
    FROM performance p
    WHERE p.product = ? AND p.scheduled_cents > 0)
SELECT a.account_id, a.app_id, a.open_date, a.channel,
       a.amount_cents,
       max(CASE WHEN d.k = 1 THEN d.missed END) >= 1 AS first_missed,
       max(CASE WHEN d.k = 3 THEN d.missed END) >= 3 AS never_paid,
       count(*) AS due_seen
FROM accounts a JOIN due d USING (account_id)
WHERE a.predecessor_id IS NULL AND d.k <= 3
GROUP BY ALL
ORDER BY a.account_id
"""


def first_payments(con=None, product: str = "personal") -> pd.DataFrame:
    """For every account of `product` (migrated cards left out), the
    first-payment markers. `never_paid` is missing where fewer than
    three payments have fallen due."""
    con = con if con is not None else fernhill.connect()
    df = con.execute(FIRST_DUE_SQL, [product]).df()
    df["never_paid"] = df["never_paid"].where(df["due_seen"] >= 3)
    return df


# ------------------------------------------------------- the rules

@dataclass(frozen=True)
class Rule:
    name: str
    text: str                                   # what it looks for
    test: Callable[[pd.DataFrame], pd.Series]   # True = flagged


def _num(apps: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(apps[col], errors="coerce").astype(float)


def _hit(apps: pd.DataFrame) -> pd.Series:
    return apps["bureau_hit"].astype(bool)


def income_ratio(apps: pd.DataFrame) -> pd.Series:
    """What verification found over what was stated; missing where the
    income was not verified."""
    ver = apps["income_verified"].astype(bool)
    r = (_num(apps, "verified_income_cents")
         / _num(apps, "stated_income_cents"))
    return r.where(ver).rename("income_ratio")


def refused_consent(apps: pd.DataFrame) -> pd.Series:
    """Asked for open-banking consent and said no (never-asked
    applicants are not refusals, however the column holds them)."""
    asked = ob_offered(apps["channel"].astype(str), apps["app_date"])
    said_no = apps["ob_consent"].astype("boolean").eq(False)
    return (asked & said_no.fillna(False)).astype(bool)


RULES = {r.name: r for r in [
    Rule("new_address", "at the current address under 9 months",
         lambda a: _num(a, "address_months") < 9),
    Rule("young_file", "bureau file under 30 months old, any age",
         lambda a: _hit(a) & (_num(a, "oldest_account_months") < 30)),
    Rule("file_younger_than_person",
         "bureau file under 30 months old at age 30 or more",
         lambda a: _hit(a) & (_num(a, "oldest_account_months") < 30)
         & (_num(a, "age") >= 30)),
    Rule("enquiry_burst", "four or more credit searches in 6 months",
         lambda a: _num(a, "enquiries_6m") >= 4),
    Rule("round_income", "stated income a whole number of thousands",
         lambda a: _num(a, "stated_income_cents") % 100_000 == 0),
    Rule("refused_consent", "asked to share bank data, said no",
         refused_consent),
    Rule("income_gap", "verified income under 70% of stated",
         lambda a: income_ratio(a) < 0.70),
]}
# The rules Ballast scores with. `young_file` is kept to show what it
# costs the young; `refused_consent` to show what it adds (§13.6).
DEFAULT = ("new_address", "file_younger_than_person", "enquiry_burst",
           "round_income", "income_gap")
REFER_AT = 3


def flags(apps: pd.DataFrame, rules=DEFAULT) -> pd.DataFrame:
    """One boolean column per rule; a rule that cannot be checked (a
    missing value) does not fire."""
    out = {name: RULES[name].test(apps) for name in rules}
    return pd.DataFrame({k: pd.Series(v, index=apps.index)
                         .fillna(False).astype(bool)
                         for k, v in out.items()}, index=apps.index)


def referred(f: pd.DataFrame, at: int = REFER_AT) -> pd.Series:
    """Applications raising `at` or more flags: to the fraud team."""
    return (f.sum(axis=1) >= at).rename("referred")


def rule_table(f: pd.DataFrame, marker) -> pd.DataFrame:
    """For each rule (and every column of `f`): how many it flagged,
    how many of the marked it caught, the share of all marked caught,
    the marked rate among the flagged, and how many unmarked rows it
    flagged for each marked one it caught."""
    m = pd.Series(np.asarray(marker, dtype=bool), index=f.index)
    rows = []
    for name in f.columns:
        hit = f[name].to_numpy()
        caught = int((hit & m).sum())
        n = int(hit.sum())
        rows.append({"rule": name, "flagged": n, "caught": caught,
                     "share_caught": caught / max(int(m.sum()), 1),
                     "precision": caught / n if n else np.nan,
                     "false_per_catch": (n - caught) / caught
                     if caught else np.inf})
    return pd.DataFrame(rows).set_index("rule")
