"""Collections: who falls behind, who comes back, and what helps.

Chapter 25's module. It reads the loan book as Chapter 6's
`performance` module prepares it (histories stitched across the
March 2022 card migration) and adds:

- Fernhill's collections ladder, written down as data;
- entries: every month end an account went from nothing missed to
  one payment missed, with what was known that day and what
  happened in the months after;
- cure and roll models fitted on entries, by logistic regression;
- the 2024 collections test: one row per account, its arm, and the
  arithmetic of comparing two arms honestly;
- forbearance flags for the 2020 payment holidays;
- the debt-sale pools: charged-off debts eligible for a sale, sold
  or kept, and what each brought in.

    import fernhill
    from ballast import collections as coll
    con = fernhill.connect()
    e = coll.entries(con, "2016-01-01", "2023-12-31")
    m = coll.fit(e[e["year"] <= 2021], "cured_3m")
    e["p_cure"] = coll.predict(m, e)

Ballast never reads the truth database, and nothing here does.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from ballast import performance as perf

# ------------------------------------------------------- the ladder

# What Fernhill's collections team does at each count of missed
# payments. Five or more is the agency; unsecured debt is charged off
# at six, so only secured debt is still with the agency beyond that.
LADDER = {1: "reminder", 2: "phone_call", 3: "final_notice",
          4: "final_notice", 5: "agency_referral"}
TEST_ACTIONS = {"call_first": "phone_call", "sms_first": "sms"}
TEST_START, TEST_END = dt.date(2024, 1, 31), dt.date(2024, 12, 31)
CHARGE_OFF_MISSED = 6
CONSUMER = ("personal", "card", "auto", "mortgage")
FAMILY = {"personal": "consumer", "card": "consumer",
          "auto": "consumer", "mortgage": "consumer",
          "sme_term": "business", "sme_overdraft": "business",
          "sme_emergency": "business"}


def ladder_action(missed: int) -> str | None:
    """The action Fernhill's ladder takes at a count of missed
    payments, outside the 2024 test."""
    if missed < 1:
        return None
    return LADDER[min(int(missed), 5)]


# ---------------------------------------------------------- entries

ENTRY_SQL = """
WITH h AS (
    SELECT root_id, account_id, product, month, balance_cents,
           limit_cents, scheduled_cents, paid_cents, missed, status,
           payment_holiday, root_open,
           lag(missed) OVER w AS prev_missed,
           lag(month) OVER w AS prev_month,
           lead(missed, 1) OVER w AS m1,
           lead(missed, 2) OVER w AS m2,
           lead(missed, 3) OVER w AS m3,
           lead(status, 1) OVER w AS s1,
           lead(status, 2) OVER w AS s2,
           lead(status, 3) OVER w AS s3,
           count(*) FILTER (WHERE missed >= 1) OVER (
               PARTITION BY root_id ORDER BY month
               ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS behind_12m,
           count(*) OVER (
               PARTITION BY root_id ORDER BY month
               ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS seen_12m
    FROM history
    WINDOW w AS (PARTITION BY root_id ORDER BY month)
)
SELECT h.root_id, h.account_id, h.product, h.month,
       h.balance_cents, h.limit_cents, h.scheduled_cents,
       h.paid_cents, h.root_open, h.behind_12m, h.seen_12m,
       h.m1, h.m2, h.m3, h.s1, h.s2, h.s3,
       mo.unemployment_pct
FROM h
JOIN macro mo ON mo.month = h.month
WHERE h.missed = 1 AND h.prev_missed = 0
  AND h.prev_month = last_day(h.month - INTERVAL 1 MONTH)
  AND h.status = 'arrears' AND NOT h.payment_holiday
  AND h.month BETWEEN ? AND ?
"""

APP_SQL = """
SELECT a.account_id, x.app_date, x.bureau_hit, x.bureau_score,
       x.bureau_version, x.channel, x.mark1_score
FROM accounts a JOIN applications x USING (app_id)
"""


def _bureau_v3(con) -> pd.DataFrame:
    """Bureau score at application on version 3's scale (Chapter 7's
    saved percentile map), for every consumer account."""
    from ballast.decision.engine import bureau_map
    from ballast.scorecard.sample import harmonised_bureau
    acc = con.execute(APP_SQL).df()
    acc["bureau_v3"] = harmonised_bureau(acc, bureau_map()).astype(float)
    return acc[["account_id", "bureau_v3", "channel", "mark1_score"]]


def entries(con, start, end, products=CONSUMER,
            outcomes: bool = True) -> pd.DataFrame:
    """Every month end an account fell one payment behind after a
    month end with nothing missed, between `start` and `end`.

    One row per entry, keyed by the root account (Chapter 6's
    stitching), with what Fernhill knew that day and the outcomes:
    `cured_1m` (nothing missed a month later), `cured_3m` (nothing
    missed three month ends later, or repaid in full before then) and
    `rolled_90` (three or more missed, or written off, at any of the
    next three month ends). Entries less than three months before the
    last month end are dropped, because their outcomes have not
    happened, unless `outcomes` is False (for scoring today's).
    """
    perf.prepare(con)
    df = con.execute(ENTRY_SQL, [pd.Timestamp(start).date(),
                                 pd.Timestamp(end).date()]).df()
    df = df[df["product"].isin(products)].copy()
    df["month"] = pd.to_datetime(df["month"])
    df["root_open"] = pd.to_datetime(df["root_open"])
    if outcomes:
        df = df[df["month"] <= pd.Timestamp(perf.AS_OF)
                - pd.offsets.MonthEnd(3)].copy()
    df["year"] = df["month"].dt.year
    df[["m1", "m2", "m3"]] = df[["m1", "m2", "m3"]].astype(float)
    mob = ((df["month"].dt.year - df["root_open"].dt.year) * 12
           + df["month"].dt.month - df["root_open"].dt.month)
    df["months_on_book"] = mob.astype(int)
    df["balance"] = df["balance_cents"] / 100
    df["log_balance"] = np.log(np.maximum(df["balance"], 50.0))
    df["behind_12m"] = df["behind_12m"].astype(int)
    df["repeat"] = (df["behind_12m"] > 0).astype(int)
    df["part_paid"] = (df["paid_cents"] > 0).astype(int)
    util = df["balance_cents"] / df["limit_cents"]
    df["utilisation"] = np.where(df["product"].eq("card"),
                                 util.clip(0, 1.5), np.nan)
    # An account repaid in full while behind has cured for good, even
    # though it has no rows after the payoff.
    wo, paid_off = perf.WRITTEN_OFF, perf.PAID_OFF
    gone = df[["s1", "s2", "s3"]].isin(paid_off).any(axis=1)
    df["cured_1m"] = df["m1"].eq(0).astype(int)
    df["cured_3m"] = (df["m3"].eq(0) | gone).astype(int)
    df["rolled_90"] = ((df[["m1", "m2", "m3"]].fillna(0) >= 3)
                       .any(axis=1)
                       | df[["s1", "s2", "s3"]].isin(wo).any(axis=1)
                       ).astype(int)
    apps = _bureau_v3(con)
    df = df.merge(apps, left_on="root_id", right_on="account_id",
                  how="left", suffixes=("", "_app"))
    df = df.drop(columns=["account_id_app"])
    # No bureau file: flagged, and given the median score so the
    # flag carries the difference. Business accounts have no consumer
    # application, so neither applies to them.
    consumer = df["product"].isin(CONSUMER)
    df["no_file"] = (consumer & df["bureau_v3"].isna()).astype(int)
    median = df.loc[consumer, "bureau_v3"].median()
    df.loc[consumer, "bureau_v3"] = df.loc[consumer, "bureau_v3"
                                           ].fillna(median)
    df = df.sort_values(["month", "root_id"]).reset_index(drop=True)
    return df


# ------------------------------------------------------------ models

FEATURES = ["bureau_v3", "no_file", "log_balance", "months_on_book",
            "behind_12m", "part_paid", "unemployment_pct",
            "is_card", "is_auto", "is_mortgage"]


def _design(df: pd.DataFrame, features) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    for f in features:
        if f.startswith("is_"):
            x[f] = df["product"].eq(f[3:]).astype(float)
        elif f == "months_on_book":
            x[f] = np.minimum(df[f], 120) / 12.0   # in years, capped
        elif f == "bureau_v3":
            x[f] = df[f] / 100.0                   # per 100 points
        else:
            x[f] = df[f].astype(float)
    return sm.add_constant(x, has_constant="add")


@dataclass
class Model:
    """A fitted logistic regression and the features it needs."""
    target: str
    features: list
    result: object

    def table(self) -> pd.DataFrame:
        r = self.result
        return pd.DataFrame({"coef": r.params, "se": r.bse,
                             "z": r.tvalues})


def fit(df: pd.DataFrame, target: str, features=None) -> Model:
    """Logistic regression of `target` on the entry's features."""
    features = list(features or FEATURES)
    x = _design(df, features)
    res = sm.Logit(df[target].astype(float), x).fit(disp=0)
    return Model(target, features, res)


def predict(model: Model, df: pd.DataFrame) -> np.ndarray:
    """Each entry's predicted chance of the model's outcome."""
    return np.asarray(model.result.predict(
        _design(df, model.features)))


# What Fernhill decided after the 2024 test (section 25.3): phone
# every account at its first missed payment, and keep one in ten on
# the old text-first treatment so the effect is still measured.
TREATMENT = {"champion": "call_first", "challenger": "sms_first",
             "challenger_share": 0.10}


def worklist(con, month, model: Model, seed: int) -> pd.DataFrame:
    """Accounts that fell one payment behind at `month`, with their
    predicted chance of cure, their treatment (champion or the
    randomly chosen challenger) and the order to work them in:
    least likely to cure first, for when calls run short."""
    w = entries(con, month, month, products=CONSUMER, outcomes=False)
    w["p_cure"] = predict(model, w)
    rng = np.random.default_rng(seed)
    test = rng.random(len(w)) < TREATMENT["challenger_share"]
    w["treatment"] = np.where(test, TREATMENT["challenger"],
                              TREATMENT["champion"])
    w["first_action"] = w["treatment"].map(TEST_ACTIONS)
    return (w.sort_values(["p_cure", "account_id"])
            .reset_index(drop=True))


# ------------------------------------------------- the 2024 test

def test_accounts(con) -> pd.DataFrame:
    """One row per account in the 2024 collections test: its first
    entry to one missed payment during 2024, its arm, its features
    and its outcomes, for every product.

    The arm belongs to the account, so an account that fell behind
    twice in 2024 was treated the same way both times; only its
    first entry counts here, so that each account is one unit.
    """
    arms = con.execute("""
        SELECT c.account_id, min(c.month) AS first_test,
               any_value(c.test_arm) AS arm, count(*) AS test_months
        FROM collections c WHERE c.test_arm IS NOT NULL
        GROUP BY 1""").df()
    e = entries(con, TEST_START, TEST_END,
                products=tuple(FAMILY))
    e = e.merge(arms, on="account_id", how="inner")
    e = (e.sort_values(["root_id", "month"])
         .drop_duplicates("root_id").reset_index(drop=True))
    e["family"] = e["product"].map(FAMILY)
    e["call"] = e["arm"].eq("call_first").astype(int)
    return e


def later_outcomes(con, df: pd.DataFrame,
                   horizon: int = 12) -> pd.DataFrame:
    """For each row of `df` (root_id, month), whether the account
    was written off within `horizon` months, the balance written
    off, and every recovery on it to date (net of costs), in cents."""
    perf.prepare(con)
    keys = df[["root_id", "month"]].copy()
    keys["month"] = pd.to_datetime(keys["month"]).dt.date
    con.register("_keys", keys)
    out = con.execute(f"""
        WITH w AS (
            SELECT k.root_id, k.month,
                   max(CASE WHEN h.status IN {perf.WRITTEN_OFF}
                       THEN 1 ELSE 0 END) AS written_off,
                   sum(CASE WHEN h.status IN {perf.WRITTEN_OFF}
                       THEN h.balance_cents ELSE 0 END) AS off_cents,
                   max(CASE WHEN h.missed >= 3 THEN 1 ELSE 0 END)
                       AS reached_90
            FROM _keys k JOIN history h
              ON h.root_id = k.root_id AND h.month > k.month
             AND h.month <= last_day(k.month
                                     + INTERVAL {horizon} MONTH)
            GROUP BY 1, 2),
        r AS (
            SELECT ar.root_id, sum(r.amount_cents) AS rec_cents
            FROM recoveries r JOIN account_root ar USING (account_id)
            GROUP BY 1)
        SELECT w.*, coalesce(r.rec_cents, 0) AS rec_cents
        FROM w LEFT JOIN r USING (root_id)""").df()
    con.unregister("_keys")
    out["month"] = pd.to_datetime(out["month"])
    out["rec_cents"] = np.where(out["written_off"].eq(1),
                                out["rec_cents"], 0)
    return out


def smd(a: pd.Series, b: pd.Series) -> float:
    """Standardised mean difference: the gap between two groups'
    means in units of their pooled standard deviation."""
    a, b = a.astype(float), b.astype(float)
    s = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return float((a.mean() - b.mean()) / s) if s > 0 else 0.0


def diff_in_proportions(x1: int, n1: int, x0: int, n0: int,
                        z: float = 1.96) -> tuple[float, float, float]:
    """Difference of two proportions, x1/n1 - x0/n0, with a normal
    (Wald) interval."""
    p1, p0 = x1 / n1, x0 / n0
    se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    d = p1 - p0
    return float(d), float(d - z * se), float(d + z * se)


def interaction_p(df: pd.DataFrame, target: str, group: str) -> float:
    """p-value that the arm's effect differs across `group`: a
    likelihood-ratio test of arm x group terms in a linear
    probability model's logistic cousin."""
    from scipy import stats
    g = pd.get_dummies(df[group], prefix="g", drop_first=True,
                       dtype=float)
    base = pd.concat([df[["call"]].astype(float), g], axis=1)
    inter = g.mul(df["call"].astype(float), axis=0).add_prefix("x_")
    y = df[target].astype(float)
    r0 = sm.Logit(y, sm.add_constant(base)).fit(disp=0)
    r1 = sm.Logit(y, sm.add_constant(pd.concat([base, inter], axis=1))
                  ).fit(disp=0)
    lr = 2 * (r1.llf - r0.llf)
    return float(stats.chi2.sf(lr, inter.shape[1]))


# ------------------------------------------------------ forbearance

HOLIDAY_FROM, HOLIDAY_TO = dt.date(2020, 4, 30), dt.date(2020, 9, 30)


def holidays(con) -> pd.DataFrame:
    """Every 2020 payment holiday: account, first and last month on
    holiday, and its length in months."""
    return con.execute("""
        SELECT account_id, min(month) AS first_month,
               max(month) AS last_month, count(*) AS months
        FROM performance WHERE payment_holiday
        GROUP BY 1 ORDER BY 1""").df()


def forborne(con, probation: int = 24) -> pd.DataFrame:
    """Account-months flagged as forborne: every month on a payment
    holiday, and the `probation` month ends after it ends. A flag a
    report carries so that arrears frozen by forbearance, and the
    months after, are never read as ordinary performance."""
    return con.execute(f"""
        WITH h AS (SELECT account_id, max(month) AS last_month
                   FROM performance WHERE payment_holiday GROUP BY 1)
        SELECT p.account_id, p.month, p.payment_holiday AS on_holiday
        FROM performance p JOIN h USING (account_id)
        WHERE p.payment_holiday
           OR (p.month > h.last_month AND p.month <=
               last_day(h.last_month + INTERVAL {probation} MONTH))
        ORDER BY 1, 2""").df()


# ------------------------------------------------------- debt sales

SALES = {dt.date(2019, 6, 30): 0.09, dt.date(2023, 11, 30): 0.12}
SALE_PRODUCTS = ("personal", "card")


def sale_pool(con, sale: dt.date, min_age: int = 6,
              max_age: int = 48) -> pd.DataFrame:
    """Charged-off personal and card debts that a sale on `sale` could
    have included: charged off between `max_age` and `min_age` months
    before it. One row per debt with `sold`, the balance written
    off, collections before the sale (gross), what was still owed on
    the sale date, the price (if sold) and every later recovery net
    of costs, all in cents."""
    rows = con.execute("""
        WITH e AS (
            SELECT a.account_id, a.product, a.close_date,
                   p.balance_cents AS off_cents
            FROM accounts a JOIN performance p
              ON p.account_id = a.account_id AND p.month = a.close_date
            WHERE a.close_reason = 'charged_off'
              AND a.product IN ('personal', 'card')
              AND a.close_date BETWEEN
                  last_day(?::DATE - INTERVAL (?) MONTH)
                  AND last_day(?::DATE - INTERVAL (?) MONTH))
        SELECT e.account_id, e.product, e.close_date, e.off_cents,
          coalesce(sum(r.amount_cents) FILTER (
              WHERE r.kind = 'collections_payment'
                AND r.month < ?), 0) AS before_gross,
          coalesce(sum(r.amount_cents) FILTER (
              WHERE r.kind IN ('collections_payment', 'cost')
                AND r.month < ?), 0) AS before_net,
          coalesce(sum(r.amount_cents) FILTER (
              WHERE r.kind = 'debt_sale' AND r.month = ?), 0)
              AS price_cents,
          coalesce(sum(r.amount_cents) FILTER (
              WHERE r.kind IN ('collections_payment', 'cost')
                AND r.month >= ?), 0) AS after_net,
          coalesce(sum(r.amount_cents) FILTER (
              WHERE r.kind = 'collections_payment' AND r.month < ?
                AND r.month > last_day(?::DATE - INTERVAL 6 MONTH)),
              0) AS last6_gross
        FROM e LEFT JOIN recoveries r USING (account_id)
        GROUP BY ALL ORDER BY e.account_id""",
        [sale, max_age, sale, min_age, sale, sale, sale, sale,
         sale, sale]).df()
    rows["sold"] = rows["price_cents"] > 0
    rows["owed_cents"] = rows["off_cents"] - rows["before_gross"]
    rows["age_months"] = [
        (sale.year - d.year) * 12 + sale.month - d.month
        for d in pd.to_datetime(rows["close_date"])]
    return rows


def later_flows(con, accounts, sale: dt.date) -> pd.DataFrame:
    """Net collections (payments less costs) by month after `sale` on
    the given accounts, in cents."""
    ids = pd.DataFrame({"account_id": list(accounts)})
    con.register("_ids", ids)
    out = con.execute("""
        SELECT r.month, sum(r.amount_cents) AS net_cents
        FROM recoveries r JOIN _ids USING (account_id)
        WHERE r.kind IN ('collections_payment', 'cost')
          AND r.month >= ?
        GROUP BY 1 ORDER BY 1""", [sale]).df()
    con.unregister("_ids")
    return out


def present_value(flows_cents, months_after, annual_rate: float
                  ) -> float:
    """Cash flows discounted to month 0 at an annual rate."""
    t = np.asarray(months_after, dtype=float)
    f = np.asarray(flows_cents, dtype=float)
    return float(np.sum(f / (1 + annual_rate) ** (t / 12)))
