"""Small businesses: the sample SME-1 is judged on, the
characteristics a data-built scorecard can use, and what the
emergency loans of 2020-21 lost.

Fernhill's small-business book sits between its consumer and
commercial books. The firms are too small for audited accounts and an
analyst's review, so they are scored, like consumers, but the score
has to read two files: the owner's and the business's. The module:

- builds the sample of booked term loans and overdrafts with a
  24-month bad flag (ever three payments behind), only for loans
  whose 24 months have passed;
- derives the characteristics: the owner's bureau score on version
  3's scale, the business score, years trading, borrowing against
  turnover, security, and the bank-account fields of applicants who
  shared them;
- adds up each defaulted emergency loan's exposure, what came back
  and from where, and what was lost.

    from ballast.commercial import sme
    s = sme.sample(con)
    losses = sme.emergency_losses(con)
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from ballast import performance as perf
from ballast.scorecard import sample as mk

PRODUCTS = ("sme_term", "sme_overdraft")
WINDOW = 24                  # months on book 1 to 24
BAD_MISSED = 3               # three payments behind: 90 days
LAST_APP = dt.date(2023, 12, 31)   # the last with a full window

# The binning spec for a data-built scorecard (ballast.scorecard).
SPEC = {
    "owner_score": {"kind": "numeric", "trend": "decreasing",
                    "decimals": -1},
    "business_score": {"kind": "numeric", "trend": "decreasing"},
    "years_trading": {"kind": "numeric", "trend": "decreasing"},
    "borrowing": {"kind": "numeric", "trend": "increasing",
                  "decimals": 2},
    "secured": {"kind": "categorical"},
    "ob_balance": {"kind": "numeric", "trend": "decreasing",
                   "decimals": 2},
    "ob_volatility": {"kind": "numeric", "trend": "increasing",
                      "decimals": 2},
    "ob_overdraft_days": {"kind": "numeric", "trend": "increasing"},
    "ob_returned_items": {"kind": "numeric", "trend": "increasing"},
}
FILE_FIELDS = ["owner_score", "business_score", "years_trading",
               "borrowing", "secured"]
BANK_FIELDS = ["ob_balance", "ob_volatility", "ob_overdraft_days",
               "ob_returned_items"]


# SME-1, Fernhill's expert scorecard for small businesses (2015), as
# its documentation sets it out. Points are added and rounded.
SME1_CUTOFFS = {dt.date(2016, 1, 1): 140, dt.date(2020, 4, 1): 150,
                dt.date(2021, 7, 1): 145}


def sme1_points(apps: pd.DataFrame) -> pd.DataFrame:
    """SME-1's points for each line, from the application's fields.

    owner      the owner's bureau score: (score - 450) / 4, held to
               0..100, on whatever scale the bureau sent
    business   the business score (1-100) x 0.9
    years      under 2 years trading 0; under 5, 20; else 35
    borrowing  (existing debt + amount asked) / turnover: under 0.15,
               40; under 0.30, 28; under 0.50, 12; else 0
    security   20 if secured
    """
    yrs = apps["years_trading"].to_numpy()
    lev = ((apps["existing_debt_cents"]
            + apps["amount_requested_cents"]).to_numpy(dtype=float)
           / np.maximum(apps["turnover_cents"].to_numpy(dtype=float),
                        1))
    out = pd.DataFrame({
        "owner": np.clip((apps["owner_bureau_score"].to_numpy(
            dtype=float) - 450) / 4, 0, 100),
        "business": apps["business_score"].to_numpy(dtype=float)
        * 0.9,
        "years": np.select([yrs < 2, yrs < 5], [0, 20], 35),
        "borrowing": np.select([lev < 0.15, lev < 0.30, lev < 0.50],
                               [40, 28, 12], 0),
        "security": np.where(apps["secured"].to_numpy(dtype=bool),
                             20, 0),
    }, index=apps.index)
    out["total"] = out.sum(axis=1).round().astype(int)
    return out


def owner_map(apps: pd.DataFrame) -> pd.Series:
    """Version-2 owner scores mapped to version 3 by percentile, on
    small-business applicants either side of the July 2019 change
    (the same method as Chapter 7's for consumers)."""
    when = pd.to_datetime(apps["app_date"]).dt.date
    frame = pd.DataFrame({"app_date": when,
                          "bureau_hit": True,
                          "bureau_score": apps["owner_bureau_score"]})
    return mk.bureau_map(frame)


def characteristics(apps: pd.DataFrame,
                    mapping: pd.Series) -> pd.DataFrame:
    """The scorecard's characteristics for any SME applications.

    owner_score     owner's bureau score, on version 3's scale
    borrowing       existing debt plus the amount asked for, over
                    turnover
    ob_balance      average balance over monthly credits (how many
                    months of takings sit in the account)
    the other ob_ fields as the bank-account data gave them; all ob_
    fields are missing where the applicant did not share its account.
    """
    v2 = pd.to_datetime(apps["app_date"]) < pd.Timestamp(
        mk.V3_HALF[0])
    owner = apps["owner_bureau_score"].astype(float)
    owner = owner.where(~v2, owner.round().astype(int).map(mapping))
    turnover = apps["turnover_cents"].astype(float)
    credits = apps["ob_monthly_credits_cents"].astype(float)
    return pd.DataFrame({
        "owner_score": owner,
        "business_score": apps["business_score"].astype(float),
        "years_trading": apps["years_trading"].astype(float),
        "borrowing": ((apps["existing_debt_cents"]
                       + apps["amount_requested_cents"]).astype(float)
                      / turnover),
        "secured": np.where(apps["secured"], "yes", "no"),
        "ob_balance": (apps["ob_avg_balance_cents"].astype(float)
                       / credits),
        "ob_volatility": apps["ob_volatility"].astype(float),
        "ob_overdraft_days": apps["ob_overdraft_days"].astype(float),
        "ob_returned_items": apps["ob_returned_items"].astype(float),
    }, index=apps.index)


def sample(con, window: int = WINDOW,
           last_app: dt.date = LAST_APP) -> pd.DataFrame:
    """Booked SME term loans and overdrafts with a known outcome.

    `bad` is 1 if the account was ever BAD_MISSED payments behind in
    months on book 1 to `window` (plain 90 days past due); `ob` is
    True where the applicant shared its bank account. Applications
    after `last_app` are too recent for the window to have passed.
    """
    apps = con.execute("""
        SELECT * FROM sme_applications ORDER BY app_id""").df()
    mapping = owner_map(apps)
    names = ", ".join(f"'{p}'" for p in PRODUCTS)
    worst = con.execute(f"""
        SELECT p.account_id,
               coalesce(max(p.missed) FILTER (WHERE datediff(
                   'month', a.open_date, p.month)
                   BETWEEN 1 AND {window}), 0) AS worst
        FROM performance p JOIN accounts a USING (account_id)
        WHERE a.product IN ({names})
        GROUP BY 1""").df()
    b = apps[(apps["outcome"] == "booked")
             & apps["product"].isin(PRODUCTS)
             & (pd.to_datetime(apps["app_date"])
                <= pd.Timestamp(last_app))]
    b = b.merge(worst, on="account_id", how="left")
    out = b[["app_id", "account_id", "app_date", "product",
             "legal_form", "sector", "sme1_score", "cutoff",
             "guarantee"]].copy()
    out["year"] = pd.to_datetime(out["app_date"]).dt.year
    out["bad"] = (b["worst"].fillna(0) >= BAD_MISSED).astype(int)
    out["ob"] = b["ob_avg_balance_cents"].notna()
    chars = characteristics(b, mapping)
    return pd.concat([out, chars], axis=1).reset_index(drop=True)


def emergency_losses(con) -> pd.DataFrame:
    """Each emergency loan in default: what was owed, what came back.

    One row per defaulted account (first default, the 2021
    definition), with the exposure at default, recoveries by kind
    (guarantee, collections_payment, cost) to December 2025, and
    whether the account has been charged off.
    """
    eps = perf.first_defaults(perf.default_episodes(
        con, "dod2021", products=["sme_emergency"]))
    rec = con.execute("""
        SELECT r.account_id, r.kind, sum(r.amount_cents) AS cents
        FROM recoveries r JOIN accounts a USING (account_id)
        WHERE a.product = 'sme_emergency'
        GROUP BY 1, 2 ORDER BY 1, 2""").df()
    wide = rec.pivot(index="account_id", columns="kind",
                     values="cents").fillna(0).astype("int64")
    closed = con.execute("""
        SELECT account_id, close_reason, open_date FROM accounts
        WHERE product = 'sme_emergency'""").df()
    out = eps[["account_id", "default_month", "ead_cents"]].merge(
        closed, on="account_id", how="left").merge(
        wide, left_on="account_id", right_index=True, how="left")
    for k in ("guarantee", "collections_payment", "cost"):
        if k not in out:
            out[k] = 0
        out[k] = out[k].fillna(0).astype("int64")
    out["charged_off"] = out["close_reason"].eq("charged_off")
    return out.sort_values("account_id").reset_index(drop=True)
