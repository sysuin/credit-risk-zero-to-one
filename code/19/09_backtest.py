# Go back to 31 December 2021, finish the unfinished workouts with
# each method, and compare with what they actually came to by 2025.
import pandas as pd

import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
CUT = pd.Timestamp("2021-12-31")
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
rates = lgd.discount_rates(con, w)
now = lgd.realised(w, f, rates)
then_w = lgd.as_at(w, CUT)          # ended later: still open then
then_f = f[pd.to_datetime(f["month"]) <= CUT]
then = lgd.realised(then_w, then_f, rates)

print("LGD of each year's defaults: as it looked in Dec 2021, as")
print("each method finished it then, and as it stood in Dec 2025")
print(f"{'product':<15}{'year':>5}{'naive':>8}{'chain':>8}"
      f"{'added':>8}{'actual':>8}")
for p in ("card", "personal", "auto", "sme_emergency"):
    tq = lgd.recovery_triangle(then_w[then_w["product"] == p], then_f,
                               rates, cohort="quarter", as_of=CUT)
    chain = lgd.completed_lgd(tq, "chain")
    add = lgd.completed_lgd(tq, "additive")
    for y in (2020, 2021):
        if str(y) not in chain:
            continue
        def pick(d):
            """This product's workouts that defaulted in year y."""
            return d[(d["product"] == p)
                     & (d["default_month"].dt.year == y)]
        naive = lgd.pooled(pick(then), by="product")["lgd"].iloc[0]
        actual = lgd.pooled(pick(now), by="product")["lgd"].iloc[0]
        print(f"{p:<15}{y:>5}{naive:>8.1%}{chain[str(y)]:>8.1%}"
              f"{add[str(y)]:>8.1%}{actual:>8.1%}")
