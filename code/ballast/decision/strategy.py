"""Strategy: where to draw the line, and what moving it changes.

A score ranks applicants; a strategy decides how many of them to
lend to. The tools here answer the questions a credit committee asks
when it sets a cut-off:

- `curve`: for each possible cut-off, the share of applicants
  approved, the bad rate expected among them, and the bad rate of
  the applicants at the margin, just above the line;
- `swap_set`: two strategies side by side, and who each approves
  that the other declines, with whatever outcomes are known;
- `choose_cutoff`: the lowest cut-off that keeps within the limits
  the committee set; `refer_band`: how wide a band holds a given
  workload;
- `loan_economics` and `break_even`: what a good loan earns and a
  bad one costs, and so the odds at which an approval pays;
- `n_per_arm` and `months_to_run`: how big and how long a
  champion-challenger test must be to detect a difference.

    from ballast.decision import strategy
    c = strategy.curve(score, p_bad, range(520, 640, 5))
    cut = strategy.choose_cutoff(c, max_bad_rate=0.04,
                                 max_marginal=0.08)
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm

# --------------------------------------------------- the trade-off


def approve_share(score, cutoff) -> float:
    """Share of applicants at or above the cut-off."""
    return float((np.asarray(score) >= cutoff).mean())


def curve(score, p_bad, cutoffs, step: float = 5) -> pd.DataFrame:
    """The strategy curve: one row per cut-off.

    `approval` is the share of applicants at or above it; `bad_rate`
    the average expected bad rate among them (`p_bad`, from the
    score's own scale); `marginal` the expected bad rate of the
    applicants in the band [cutoff, cutoff + step), the last ones the
    cut-off lets in; `bads` the expected number of bads approved.
    """
    s = np.asarray(score, dtype=float)
    p = np.asarray(p_bad, dtype=float)
    rows = []
    for c in cutoffs:
        ap = s >= c
        edge = ap & (s < c + step)
        rows.append({"cutoff": c, "approved": int(ap.sum()),
                     "approval": float(ap.mean()),
                     "bad_rate": float(p[ap].mean()) if ap.any()
                     else np.nan,
                     "marginal": float(p[edge].mean()) if edge.any()
                     else np.nan,
                     "bads": float(p[ap].sum())})
    return pd.DataFrame(rows)


def cutoff_for_share(score, share: float) -> int:
    """The cut-off whose approval share is closest to `share`."""
    s = np.asarray(score)
    best, gap = None, np.inf
    for c in np.unique(s):
        g = abs((s >= c).mean() - share)
        if g < gap - 1e-12:
            best, gap = int(c), g
    return best


def choose_cutoff(c: pd.DataFrame, max_bad_rate: float,
                  max_marginal: float) -> int:
    """The lowest cut-off at which the expected bad rate of everyone
    approved is within `max_bad_rate` and the marginal band's within
    `max_marginal`. Lower cut-offs approve more, so the lowest that
    keeps within both limits is the one a lender wants."""
    ok = c[(c["bad_rate"] <= max_bad_rate)
           & (c["marginal"] <= max_marginal)]
    if ok.empty:
        raise ValueError("no cut-off keeps within both limits")
    return int(ok["cutoff"].min())


def refer_band(score, cutoff: int, share: float) -> int:
    """The half-width w (in points) of the band [cutoff - w, cutoff +
    w) that holds as near as possible `share` of applicants without
    exceeding it: a refer band sized to a workload."""
    s = np.asarray(score)
    w = 0
    while w < 100:
        nxt = ((s >= cutoff - (w + 1)) & (s < cutoff + w + 1)).mean()
        if nxt > share:
            break
        w += 1
    return w


# ------------------------------------------------------- swap sets

SWAP_ORDER = ["both approve", "only A approves", "only B approves",
              "both decline"]


def swap_set(approve_a, approve_b, outcome=None,
             promised=None) -> pd.DataFrame:
    """Two strategies' decisions cross-tabulated.

    `outcome` is 1 for bad, 0 for good and NaN where unknown; each
    cell reports how many have an outcome and their bad rate.
    `promised` is a score's expected bad rate, averaged per cell.
    """
    a = np.asarray(approve_a, dtype=bool)
    b = np.asarray(approve_b, dtype=bool)
    cells = {"both approve": a & b, "only A approves": a & ~b,
             "only B approves": ~a & b, "both decline": ~a & ~b}
    y = (np.full(len(a), np.nan) if outcome is None
         else np.asarray(outcome, dtype=float))
    rows = []
    for name in SWAP_ORDER:
        m = cells[name]
        known = m & ~np.isnan(y)
        row = {"cell": name, "n": int(m.sum()),
               "known": int(known.sum()),
               "bad_rate": float(y[known].mean()) if known.any()
               else np.nan}
        if promised is not None:
            pr = np.asarray(promised, dtype=float)
            row["promised"] = float(pr[m].mean()) if m.any() \
                else np.nan
        rows.append(row)
    return pd.DataFrame(rows).set_index("cell")


def top_share(score, share: float) -> np.ndarray:
    """Approve exactly round(share x n) applicants, highest scores
    first (ties broken by position): two scores compared at the same
    approval rate."""
    s = np.asarray(score, dtype=float)
    k = int(round(share * len(s)))
    order = np.argsort(-s, kind="stable")
    out = np.zeros(len(s), dtype=bool)
    out[order[:k]] = True
    return out


# -------------------------------------------------- what a loan earns

ECONOMICS_SQL = """
WITH p AS (
    SELECT p.account_id, p.month, p.balance_cents, p.paid_cents,
           lag(p.balance_cents) OVER (PARTITION BY p.account_id
                                      ORDER BY p.month) AS owed,
           m.cost_of_funds_pct
    FROM performance p JOIN market_rates m ON m.month = p.month
    WHERE p.product = ?),
cash AS (
    SELECT account_id, sum(paid_cents) AS paid,
           sum(coalesce(owed, 0) * cost_of_funds_pct / 1200.0)
               AS funding,
           sum(coalesce(owed, 0)) AS owed_months,
           arg_max(balance_cents, month) AS last_balance
    FROM p GROUP BY account_id),
rec AS (SELECT account_id, sum(amount_cents) AS recovered
        FROM recoveries GROUP BY account_id)
SELECT a.account_id, a.app_id, a.open_date, a.close_reason,
       a.amount_cents, c.paid, c.funding, c.owed_months,
       c.last_balance, coalesce(r.recovered, 0) AS recovered
FROM accounts a JOIN cash c USING (account_id)
LEFT JOIN rec r USING (account_id)
WHERE a.product = ? ORDER BY a.account_id
"""


def loan_economics(con, product: str = "personal",
                   opex_pct: float = 2.5) -> pd.DataFrame:
    """Each loan's cash result to 31 December 2025, in cents.

    Money in (every payment, every recovery net of its costs, and
    the balance still owed on a loan that is still open) less
    money out (the amount lent, the cost of funding the balance month
    by month at Fernhill's cost of funds, and an operating cost of
    `opex_pct` of the balance a year). Nothing is discounted.
    """
    d = con.execute(ECONOMICS_SQL, [product, product]).df()
    still_owed = np.where(d["close_reason"].isna(), d["last_balance"],
                          0)
    d["opex"] = d["owed_months"] * opex_pct / 1200
    d["profit"] = (d["paid"] + d["recovered"] + still_owed
                   - d["amount_cents"] - d["funding"] - d["opex"])
    for col in ("funding", "opex", "profit"):
        d[col] = d[col].round().astype(np.int64)
    return d.drop(columns=["owed_months", "last_balance"])


def break_even(good_earns: float, bad_costs: float) -> tuple[float,
                                                             float]:
    """The good:bad odds at which approving pays nothing either way,
    and the bad rate they imply. Above those odds an approval earns
    money on average; below them it loses."""
    odds = bad_costs / good_earns
    return odds, 1 / (1 + odds)


# ----------------------------------------- champion-challenger tests

def n_per_arm(p1: float, p2: float, alpha: float = 0.05,
              power: float = 0.80) -> int:
    """Loans needed in each arm for a two-sided test of two bad rates
    to detect p1 against p2 with the given power."""
    za = norm.ppf(1 - alpha / 2)
    zb = norm.ppf(power)
    var = p1 * (1 - p1) + p2 * (1 - p2)
    return math.ceil((za + zb) ** 2 * var / (p1 - p2) ** 2)


def months_to_run(n: int, per_month: float, share: float,
                  window: int = 12) -> int:
    """Months from the first application to the last outcome: time to
    gather `n` loans when `share` of `per_month` go to the arm, plus
    the outcome window and one month to read it."""
    return math.ceil(n / (per_month * share)) + window + 1


def detectable(p1: float, n: int, alpha: float = 0.05,
               power: float = 0.80) -> float:
    """The lowest bad rate p2 below p1 that a test of `n` loans an arm
    would detect with the given power: what a test of that size can
    and cannot tell apart."""
    lo, hi = 0.0, p1
    for _ in range(60):
        mid = (lo + hi) / 2
        if mid >= p1 or n_per_arm(p1, mid, alpha, power) > n:
            hi = mid
        else:
            lo = mid
    return lo
