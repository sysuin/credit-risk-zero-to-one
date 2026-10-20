# Exercise 1: the absolute guard in the SICR rule at half a point and
# two points, with the ratio at 2, staged a year back.
# timeout: 300
import datetime as dt

import fernhill
import numpy as np
import pandas as pd
from ballast import ecl
from ballast import performance as perf

DATE = dt.date(2024, 12, 31)
con = fernhill.connect()
eps = perf.default_episodes(con)
dm = pd.to_datetime(eps["default_month"])
r = ecl.run(con, DATE, ecl.parameters(con, DATE))
t0 = pd.Timestamp(DATE)
nxt = set(eps["account_id"][(dm > t0)
                            & (dm <= t0 + pd.DateOffset(years=1))])
fac = {x[0] for x in con.execute(
    """SELECT facility_id FROM facility_months
       WHERE status = 'defaulted'
       AND month > ? AND month <= ?""",
    [DATE, (t0 + pd.DateOffset(years=1)).date()]).fetchall()}
y = np.where(r["segment"] == "retail", r["root_id"].isin(nxt),
             r["account_id"].isin(fac))
live = (r["stage"] < 3).to_numpy()
yl = y[live]
print(f"{'points':>7}{'stage 2':>9}{'stage 2 DR':>12}{'caught':>8}"
      f"{'cards in 2':>12}")
for pts in (0.005, 0.01, 0.02):
    st = ecl.stage(r[live], 2.0, pts)["stage"].to_numpy()
    two = st == 2
    cards = (two & (r.loc[live, "product"] == "card").to_numpy()).sum()
    print(f"{pts * 100:>7.1f}{two.mean():>9.1%}{yl[two].mean():>12.1%}"
          f"{yl[two].sum() / yl.sum():>8.0%}{cards:>12,}")
