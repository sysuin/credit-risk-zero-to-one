# Exercise 24.4: the early-warning list held to five clients a month
# on average. Which revolver threshold, and what does it still catch?
import pandas as pd

import fernhill
from ballast import monitoring as mon

con = fernhill.connect()
p = mon.business_panel(con)
w = mon.watch(p)
months = p.loc[p.default_12m.notna(), "month"].nunique()
print(f"{'drawn':<7}{'a month':>9}{'hit rate':>10}{'caught':>8}"
      f"{'false alarms':>14}")
for k in (0.75, 0.80, 0.85, 0.90):
    up = (p["revolver_use"] - p["use_at_review"]) >= 0.15
    flag = pd.DataFrame({"x": (p["revolver_use"] >= k)
                         | (up & (p["revolver_use"] >= k - 0.15))
                         | w["market"]})
    r = mon.watch_record(p, flag).iloc[0]
    print(f"{k:<7.0%}{r.months / months:>9.1f}{r.hit_rate:>10.1%}"
          f"{r.caught:>5} of {r.defaults}{r.false_alarms:>11}")
