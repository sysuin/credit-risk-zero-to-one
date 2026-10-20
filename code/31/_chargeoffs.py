"""Chapter 31's helper: personal-loan charge-offs by month, cohort and
age, the rate model, and the decomposition of each year's dollars into
the book, the economy, cohort quality and chance.

Not printed in full; §31.3 shows the parts that matter. The runner
skips files that start with an underscore and tracks this one as a
dependency of the listings that import it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from ballast.parameters import pd as pdm

# Cohorts by the month the loan was opened, named by the lending policy
# in force (DECISIONS.md, Chapter 11). The last is today's policy and
# is the yardstick every other cohort is measured against.
COHORTS = [("2016-2018", "2016-01"),
           ("Jan 2019-Mar 2020", "2019-01"),
           ("Apr 2020-Jan 2021", "2020-04"),
           ("the push", "2021-02"),
           ("since Jul 2022", "2022-07")]
REFERENCE = "since Jul 2022"
PUSH = "the push"
AGES = [(6, 11), (12, 17), (18, 23), (24, 35), (36, 999)]
REF_AGE = "12-17"
LAG = 6          # months between unemployment and the charge-off
FIRST = "2017-01-01"   # unemployment exists LAG months back from here

MONTHS_SQL = """
WITH p AS (
    SELECT p.account_id, p.month, p.status, p.balance_cents,
           lag(p.status) OVER w        AS prev_status,
           lag(p.balance_cents) OVER w AS prev_cents,
           datediff('month', a.open_date, p.month) AS mob,
           a.open_date
    FROM performance p JOIN accounts a USING (account_id)
    WHERE p.product = 'personal'
    WINDOW w AS (PARTITION BY p.account_id ORDER BY p.month))
SELECT account_id, month, open_date, mob,
       prev_cents AS risk_cents,
       CASE WHEN status = 'charged_off' THEN balance_cents ELSE 0 END
           AS off_cents
FROM p
WHERE prev_status IN ('up_to_date', 'arrears', 'default')
ORDER BY account_id, month
"""


def cohort_of(open_date: pd.Series) -> pd.Series:
    """The policy cohort of each loan, from its opening month."""
    m = pd.to_datetime(open_date).dt.to_period("M")
    out = pd.Series(COHORTS[0][0], index=open_date.index)
    for name, start in COHORTS[1:]:
        out[m >= pd.Period(start)] = name
    return out


def age_of(mob: pd.Series) -> pd.Series:
    out = pd.Series("", index=mob.index)
    for lo, hi in AGES:
        label = f"{lo}-{hi}" if hi < 999 else f"{lo}+"
        out[mob.between(lo, hi)] = label
    return out


def account_months(con) -> pd.DataFrame:
    """Every month a personal loan was open at the previous month end:
    the balance then (at risk) and what was charged off this month.
    Ages below six months are dropped: a loan is charged off at six
    missed payments, so none can be younger."""
    m = con.execute(MONTHS_SQL).df()
    m = m[m["mob"] >= AGES[0][0]].copy()
    m["month"] = pd.to_datetime(m["month"])
    m["cohort"] = cohort_of(m["open_date"])
    m["age"] = age_of(m["mob"])
    return m


def unemployment(con, lag: int = LAG) -> pd.Series:
    """Unemployment `lag` months before each month end."""
    u = con.execute("SELECT month, unemployment_pct FROM macro "
                    "ORDER BY month").df()
    s = pd.Series(u["unemployment_pct"].to_numpy(),
                  index=pd.to_datetime(u["month"]))
    s.index = s.index + pd.offsets.MonthEnd(lag)
    return s


def cells(m: pd.DataFrame, u: pd.Series, first: str = FIRST
          ) -> pd.DataFrame:
    """Month x cohort x age: dollars at risk, dollars charged off, and
    unemployment LAG months before."""
    c = (m.groupby(["month", "cohort", "age"], observed=True)
         .agg(risk=("risk_cents", "sum"), off=("off_cents", "sum"))
         .reset_index())
    c = c[(c["risk"] > 0) & (c["month"] >= first)].copy()
    c["u"] = c["month"].map(u)
    c["year"] = c["month"].dt.year
    return c.reset_index(drop=True)


def design(c: pd.DataFrame, long_run: float) -> pd.DataFrame:
    """Columns: a constant, one per age band and cohort other than the
    reference ones, and unemployment's distance from its long run."""
    X = pd.DataFrame({"const": 1.0}, index=c.index)
    for lo, hi in AGES:
        a = f"{lo}-{hi}" if hi < 999 else f"{lo}+"
        if a != REF_AGE:
            X[f"age {a}"] = (c["age"] == a).astype(float)
    for name, _ in COHORTS:
        if name != REFERENCE:
            X[name] = (c["cohort"] == name).astype(float)
    X["u"] = c["u"] - long_run
    return X


def fit(c: pd.DataFrame, long_run: float):
    """Charge-off dollars per dollar at risk: a log-linear (Poisson)
    rate model, with its variance scaled to what the data show."""
    X = design(c, long_run)
    return sm.GLM(c["off"] / 100, X, family=sm.families.Poisson(),
                  offset=np.log(c["risk"] / 100)).fit(scale="X2")


def long_run_u(con) -> float:
    return pdm.long_run_unemployment(con)


def expected(c: pd.DataFrame, b: pd.Series, long_run: float,
             economy: bool, quality: bool) -> np.ndarray:
    """Expected dollars in each cell with the economy and cohort
    quality switched on or off (off: unemployment at its long run,
    every cohort as good as today's)."""
    X = design(c, long_run)
    if not economy:
        X["u"] = 0.0
    if not quality:
        for name, _ in COHORTS:
            if name != REFERENCE:
                X[name] = 0.0
    eta = X.to_numpy() @ b[X.columns].to_numpy()
    return (c["risk"].to_numpy() / 100) * np.exp(eta)


def components(c: pd.DataFrame, b: pd.Series, long_run: float
               ) -> pd.DataFrame:
    """Each cell's dollars split four ways. The economy and quality
    effects are each the average of their effect with the other on and
    off (a Shapley split), so the four add up to what was charged
    off."""
    e00 = expected(c, b, long_run, False, False)
    e10 = expected(c, b, long_run, True, False)
    e01 = expected(c, b, long_run, False, True)
    e11 = expected(c, b, long_run, True, True)
    out = c[["year", "cohort", "age"]].copy()
    out["actual"] = c["off"].to_numpy() / 100
    out["book"] = e00
    out["economy"] = ((e10 - e00) + (e11 - e01)) / 2
    out["quality"] = ((e01 - e00) + (e11 - e10)) / 2
    out["fitted"] = e11
    out["chance"] = out["actual"] - e11
    return out


PARTS = ["book", "economy", "quality", "chance"]


def by_year(comp: pd.DataFrame) -> pd.DataFrame:
    t = comp.groupby("year")[["actual"] + PARTS + ["fitted"]].sum()
    push = comp[comp.cohort == PUSH]
    t["push"] = push.groupby("year")["quality"].sum()
    return t.fillna(0.0)


def draws(res, n: int, rng) -> pd.DataFrame:
    """Coefficient vectors drawn from the fit's estimated sampling
    distribution, for intervals on anything computed from them."""
    return pd.DataFrame(rng.multivariate_normal(res.params,
                                                res.cov_params(), n),
                        columns=res.params.index)
