"""Helpers the Chapter 12 listings share: personal-loan applications
scored by Mark II-R, and each booked loan's months at risk."""
import pandas as pd

from ballast import data
from ballast.decision import engine
from ballast.decision import policy as pol

COLUMNS = ["app_id", "app_date", "channel", "mark1_score", "decision",
           "decline_reason", "override", "offered_rate_pct",
           "offered_amount_cents", "term_requested_months",
           "amount_requested_cents", "price_test_arm", "outcome",
           "account_id"]


def scored(con) -> pd.DataFrame:
    """Every personal-loan application with its Mark II-R score."""
    raw = data.load_applications(con, unknowns=False)
    raw = raw[raw["product"].astype(str).eq("personal")]
    card = engine.load_champion(pol.load_policy())
    out = raw[COLUMNS].copy()
    out["m2r"] = card.score(engine.prepare(raw)).to_numpy()
    out["app_date"] = pd.to_datetime(out["app_date"])
    for c in ("channel", "decision", "outcome", "price_test_arm",
              "override", "decline_reason"):
        out[c] = out[c].astype(object)
    return out.reset_index(drop=True)


RISK_SQL = """
WITH p AS (
    SELECT p.account_id, p.month, p.missed, p.status,
           datediff('month', a.open_date, p.month) AS mob,
           min(p.month) FILTER (WHERE p.missed >= 3)
               OVER (PARTITION BY p.account_id) AS defaulted
    FROM performance p JOIN accounts a USING (account_id)
    WHERE a.product = 'personal')
SELECT account_id,
       count(*) FILTER (WHERE mob >= 1) AS months,
       max(CASE WHEN month = defaulted THEN 1 ELSE 0 END) AS dflt,
       max(CASE WHEN status = 'prepaid' THEN 1 ELSE 0 END) AS prepaid
FROM p WHERE defaulted IS NULL OR month <= defaulted
GROUP BY 1 ORDER BY 1
"""


def at_risk(con) -> pd.DataFrame:
    """Each personal loan's months at risk, from its first month with
    a payment due until it defaults (three missed payments), closes
    or reaches December 2025; whether it defaulted, or prepaid."""
    return con.execute(RISK_SQL).df()


def book_rates(con, a: pd.DataFrame):
    """Listing 02's fits, repeated: the default and prepayment curves
    on loans applied for 2019-2023, and the loss given default."""
    from ballast import pricing
    loans = a[a["outcome"].eq("booked")
              & a["app_date"].between("2019-01-01", "2023-12-31")]
    d = loans[["account_id", "m2r"]].merge(at_risk(con),
                                           on="account_id")
    fd = pricing.fit_hazard(d["m2r"], d["dflt"], d["months"])
    fp = pricing.fit_hazard(d["m2r"], d["prepaid"], d["months"])
    owed, back = con.execute(LGD_SQL).fetchone()
    return fd, fp, round(1 - back / owed, 2)


LGD_SQL = """
WITH p AS (
    SELECT p.*, min(p.month) FILTER (WHERE p.missed >= 3)
               OVER (PARTITION BY account_id) AS dm
    FROM performance p WHERE product = 'personal'),
d AS (
    SELECT account_id,
           max(balance_cents) FILTER (WHERE month = dm) AS ead,
           coalesce(sum(paid_cents) FILTER (WHERE month > dm), 0)
               AS after
    FROM p WHERE dm < DATE '2023-01-01' GROUP BY 1)
SELECT sum(ead), sum(after) + sum(coalesce(r.rec, 0))
FROM d LEFT JOIN (SELECT account_id, sum(amount_cents) AS rec
                  FROM recoveries GROUP BY 1) r USING (account_id)
"""


def market(con, month: str = "2025-12-31") -> dict:
    """One month's rates from `market_rates`, as a dict."""
    return con.execute(
        "SELECT policy_rate_pct, cost_of_funds_pct, swap_2y_pct, "
        "swap_5y_pct FROM market_rates WHERE month = ?",
        [month]).df().iloc[0].to_dict()


def mark1_tier(score) -> pd.Series:
    """Fernhill's price tiers on Mark I, as drawn in April 2019."""
    return pd.cut(pd.Series(score), [0, 600, 630, 660, 999],
                  right=False,
                  labels=["<600", "600-629", "630-659", "660+"])
