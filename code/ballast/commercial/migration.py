"""Rating migration: where each grade's borrowers are a year later,
and how often each grade defaulted against the PD it promised.

A migration matrix counts, for every client graded g at one annual
review, its grade at the next review, or D if it defaulted in
between. Read across a row and you have that grade's year ahead; the
last column is its default rate. The module:

- builds the panel of review-to-review moves from `rating.reviews`,
  for the analysts' grades or the model's;
- counts the matrix and turns it into shares by row;
- summarises how far grades move in a year;
- sets each grade's observed default rate against the master scale,
  with an exact binomial interval and test;
- projects a matrix over several years.

    from ballast.commercial import rating as rt, migration as mg
    rv = rt.reviews(con)
    p = mg.panel(rv, "grade")
    counts = mg.matrix(p, shares=False)
    mg.default_rates(rv[rv.window_complete], "grade", "default_12m")
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import beta, binomtest

from ballast.commercial.rating import DEFAULT, GRADES, MASTER_SCALE

STATES = [str(g) for g in GRADES] + [DEFAULT]


def panel(rv: pd.DataFrame, column: str = "grade") -> pd.DataFrame:
    """One row per review: the grade, and the state a year later.

    `after` is the grade at the client's next review, or D if it
    defaulted within the 12 months after this one. A review whose
    year has not finished, and whose client has no later review,
    has no `after` and is left out.
    """
    r = rv.sort_values(["company_id", "review_date"])
    nxt = r.groupby("company_id")[column].shift(-1)
    after = nxt.astype("Int64").astype(str)
    after = after.where(nxt.notna(), None)
    after = after.where(r["default_12m"] == 0, DEFAULT)
    out = pd.DataFrame({"company_id": r["company_id"],
                        "review_date": r["review_date"],
                        "before": r[column].astype(int).astype(str),
                        "after": after})
    return out[out["after"].notna()].reset_index(drop=True)


def matrix(p: pd.DataFrame, shares: bool = True) -> pd.DataFrame:
    """Grades now (rows) by state a year later (columns)."""
    t = pd.crosstab(p["before"], p["after"])
    t = t.reindex(index=STATES[:-1], columns=STATES, fill_value=0)
    if shares:
        t = t.div(t.sum(axis=1).replace(0, np.nan), axis=0)
    t.index.name, t.columns.name = "from", "to"
    return t


def summary(p: pd.DataFrame) -> dict:
    """How far grades moved in a year, among clients not in default.

    stayed, one notch, two notches, three or more: shares of moves;
    up and down: shares that improved or worsened.
    """
    q = p[p["after"] != DEFAULT]
    step = q["after"].astype(int) - q["before"].astype(int)
    n = len(step)
    return {"moves": n,
            "stayed": float((step == 0).mean()),
            "one": float((step.abs() == 1).mean()),
            "two": float((step.abs() == 2).mean()),
            "three_plus": float((step.abs() >= 3).mean()),
            "down": float((step > 0).sum() / n),
            "up": float((step < 0).sum() / n)}


def interval(defaults: int, n: int, level: float = 0.95
             ) -> tuple[float, float]:
    """An exact (Clopper-Pearson) interval for a default rate."""
    a = (1 - level) / 2
    lo = 0.0 if defaults == 0 else beta.ppf(a, defaults,
                                            n - defaults + 1)
    hi = 1.0 if defaults == n else beta.ppf(1 - a, defaults + 1,
                                            n - defaults)
    return float(lo), float(hi)


def default_rates(rv: pd.DataFrame, column: str = "grade",
                  bad: str = "default_12m",
                  scale: dict = MASTER_SCALE) -> pd.DataFrame:
    """Each grade's observed default rate against its promised PD.

    `p_value` is a two-sided exact binomial test of the observed
    count against the promised PD: small means the grade's record and
    its PD are hard to reconcile. With few defaults, read the interval
    before the point estimate.
    """
    rows = []
    for g in GRADES:
        sel = rv[rv[column] == g]
        n, d = len(sel), int(sel[bad].sum())
        lo, hi = interval(d, n) if n else (np.nan, np.nan)
        rows.append({"grade": g, "n": n, "defaults": d,
                     "observed": d / n if n else np.nan,
                     "promised": scale[g],
                     "expected": n * scale[g],
                     "lower": lo, "upper": hi,
                     "p_value": binomtest(d, n, scale[g]).pvalue
                     if n else np.nan})
    return pd.DataFrame(rows).set_index("grade")


def project(shares: pd.DataFrame, years: int) -> pd.DataFrame:
    """Cumulative default rate by grade over 1..`years` years, if
    every year moved like the matrix (D is never left)."""
    m = shares.fillna(0).to_numpy()
    full = np.vstack([m, np.eye(len(STATES))[-1]])
    step = np.eye(len(STATES))
    out = {}
    for y in range(1, years + 1):
        step = step @ full
        out[y] = step[:-1, -1]
    return pd.DataFrame(out, index=shares.index)
