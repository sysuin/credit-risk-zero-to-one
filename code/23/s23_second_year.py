# Exercise 23.1: the definition question for a loan's second year.
# Development loans followed through months 13 to 24, first defaults
# counted both ways, and Mark II-R's ranking of each.
import pandas as pd

import fernhill
from ballast import performance as perf
from ballast.scorecard import metrics, reject, sample

con = fernhill.connect()
s = sample.load_sample()
s = s[s["split"].isin(["train", "holdout"])
      & (s["outcome"] != "bad")].copy()
s["score"] = reject.load_refit("mark2_retro_ws").scorecard().score(s)
om = pd.to_datetime(s["open_date"]) + pd.offsets.MonthEnd(0)
for d in ("dpd90", "dod2021"):
    e = perf.first_defaults(perf.default_episodes(
        con, d, products=["personal"]))
    s = s.merge(e[["account_id", "default_month", "trigger"]].rename(
        columns={"default_month": d, "trigger": d + "_why"}),
        on="account_id", how="left")
    dm = pd.to_datetime(s[d])
    mob = (dm.dt.year - om.dt.year) * 12 + dm.dt.month - om.dt.month
    s[d + "_y2"] = mob.between(13, 24).astype(int)
print(f"{len(s):,} development loans not bad in their first year")
print(f"{'definition':<12}{'defaults, months 13-24':>24}"
      f"{'bankruptcy':>12}{'Gini':>8}")
for d in ("dpd90", "dod2021"):
    y = s[d + "_y2"]
    bk = ((y == 1) & (s[d + "_why"] == "bankruptcy")).sum()
    print(f"{d:<12}{y.sum():>24,}{bk:>12}"
          f"{metrics.gini(s['score'], y):>8.3f}")
both = ((s["dpd90_y2"] == 1) & (s["dod2021_y2"] == 1)).sum()
print(f"Counted by both: {both}")
