# Choosing the threshold for a significant increase in credit risk:
# stage the book a year back several ways and see who defaulted next.
# timeout: 300
import datetime as dt

import fernhill
import numpy as np
import pandas as pd
from ballast import ecl
from ballast import performance as perf

con = fernhill.connect()
eps = perf.default_episodes(con)
dm = pd.to_datetime(eps["default_month"])
print(f"{'date':<11}{'rule':<10}{'stage 2':>8}"
      f"{'defaulted next year':>27}{'caught':>8}")
print(f"{'':<21}{'share':>8}{'stage 2':>9}{'added':>9}{'stage 1':>9}")
for date in (dt.date(2023, 12, 31), dt.date(2024, 12, 31)):
    r = ecl.run(con, date, ecl.parameters(con, date))
    t0 = pd.Timestamp(date)
    t1 = t0 + pd.DateOffset(months=12)
    nxt = set(eps["account_id"][(dm > t0) & (dm <= t1)])
    fac = {x[0] for x in con.execute(
        """SELECT facility_id FROM facility_months
           WHERE status = 'defaulted' AND month > ? AND month <= ?""",
        [date, t1.date()]).fetchall()}
    y = np.where(r["segment"] == "retail", r["root_id"].isin(nxt),
                 r["account_id"].isin(fac))
    live = (r["stage"] < 3).to_numpy()
    yl = y[live]
    back = (ecl.stage(r[live], np.inf)["stage"] == 2).to_numpy()
    for name, ratio in [("1.5x", 1.5), ("2x", 2.0), ("3x", 3.0),
                        ("backstops", np.inf)]:
        st = ecl.stage(r[live], ratio, ecl.SICR_POINTS)["stage"]
        two = (st == 2).to_numpy()
        add = two & ~back
        added = f"{yl[add].mean():>9.1%}" if add.any() else f"{'-':>9}"
        print(f"{str(date):<11}{name:<10}{two.mean():>8.1%}"
              f"{yl[two].mean():>9.1%}{added}{yl[~two].mean():>9.1%}"
              f"{yl[two].sum() / yl.sum():>8.0%}")
print("rule: 12-month PD at least that multiple of origination's and")
print("one point higher, plus the backstops (30 days past due, a")
print("year after a cure, the commercial watchlist); added: accounts")
print("the PD test adds to the backstops; caught: share of next")
print("year's defaults already in stage 2")
