# Exercise 19.2: the backtest of listing 09, as at 31 December 2022.
import pandas as pd

import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
CUT = pd.Timestamp("2022-12-31")
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
rates = lgd.discount_rates(con, w)
now = lgd.realised(w, f, rates)
then_w = lgd.as_at(w, CUT)
then_f = f[pd.to_datetime(f["month"]) <= CUT]
then = lgd.realised(then_w, then_f, rates)
print(f"{'product':<10}{'year':>5}{'naive':>8}{'chain':>8}"
      f"{'added':>8}{'actual':>8}")
for p in ("card", "personal"):
    tq = lgd.recovery_triangle(then_w[then_w["product"] == p], then_f,
                               rates, cohort="quarter", as_of=CUT)
    chain = lgd.completed_lgd(tq, "chain")
    add = lgd.completed_lgd(tq, "additive")
    for y in (2021, 2022):
        def pick(d):
            return d[(d["product"] == p)
                     & (d["default_month"].dt.year == y)]
        naive = lgd.pooled(pick(then))["lgd"].iloc[0]
        actual = lgd.pooled(pick(now))["lgd"].iloc[0]
        print(f"{p:<10}{y:>5}{naive:>8.1%}{chain[str(y)]:>8.1%}"
              f"{add[str(y)]:>8.1%}{actual:>8.1%}")
