# Exercise 11.2: the swap set between Mark II and Mark II-R, applicants
# of 2023, both approving as many as Mark II-R does at 554.
import numpy as np
import pandas as pd

from ballast.decision import strategy
from ballast.scorecard import points, reject

a = reject.frames(reject.applicants())["oot"]
a = a.merge(reject.retro(), on="app_id", how="left")
year = pd.to_datetime(a["app_date"].astype("datetime64[s]")).dt.year
a = a[year == 2023].reset_index(drop=True)
m2r = reject.load_refit("mark2_retro_ws").scorecard().score(a)
share = (m2r >= 554).mean()
new = strategy.top_share(m2r, share)
old = strategy.top_share(points.load_scorecard().score(a), share)
elsewhere = a["opened_elsewhere"].fillna(False).astype(bool)
seen = np.where(a["known"], a["bad"],
                np.where(elsewhere, a["bad_elsewhere"], np.nan))
t = strategy.swap_set(new, old, seen, points.bad_rate_at(m2r))
t.index = ["both", "only Mark II-R", "only Mark II", "neither"]
print(f"2023, both approving {share:.1%}")
print(f"  {'':<16}{'people':>7}{'seen':>7}{'bad rate':>10}")
for name, r in t.iterrows():
    print(f"  {name:<16}{int(r['n']):>7,}{int(r['known']):>7,}"
          f"{r['bad_rate']:>10.1%}")
ws = a.loc[new & ~old, "worst_status_24m"]
print(f"  only Mark II-R with a late payment on file: "
      f"{(ws >= 30).mean():.0%}")
ws = a.loc[~new & old, "worst_status_24m"]
print(f"  only Mark II with a late payment on file:   "
      f"{(ws >= 30).mean():.0%}")
