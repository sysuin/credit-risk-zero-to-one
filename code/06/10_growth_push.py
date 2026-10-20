# The growth push against its neighbours, measured fairly: personal
# loans grouped by the lending policy they were booked under, each
# group's default rate at the same months on book.
import numpy as np
import pandas as pd

import fernhill
from ballast import performance as perf
from ballast.config import AS_OF

PERIODS = [("Jan 2019-Mar 2020", "cut-off 575", "2019-01", "2020-03"),
           ("Apr 2020-Jan 2021", "cut-off 610", "2020-04", "2021-01"),
           ("Feb 2021-Jun 2022", "the push, 525", "2021-02", "2022-06"),
           ("Jul 2022-Dec 2023", "cut-off 580", "2022-07", "2023-12"),
           ("Jan 2024-Dec 2024", "cut-off 580", "2024-01", "2024-12")]
con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")
acc = perf.cohort_accounts(con, "personal", eps)
macro = con.execute("SELECT month, unemployment_pct FROM macro").df()
jobless = pd.Series(macro["unemployment_pct"].to_numpy(),
                    index=pd.to_datetime(macro["month"]))
last = pd.Timestamp(AS_OF)
print(f"{'booked':<19}{'policy':<15}{'loans':>6}{'m12':>7}{'m18':>7}"
      f"{'jobless':>9}")
for name, policy, lo, hi in PERIODS:
    booked = acc["open_month"].dt.to_period("M")
    g = acc[booked.between(pd.Period(lo), pd.Period(hi))]
    youngest = g["open_month"].max()
    seen = ((last.year - youngest.year) * 12
            + last.month - youngest.month)
    cells = ""
    for k in (12, 18):
        rate = (g["default_mob"] <= k).mean()
        cells += f"{rate:>7.2%}" if k <= seen else f"{'.':>7}"
    # unemployment over each loan's first twelve months, averaged
    first_year = [jobless[m + pd.offsets.MonthEnd(1):
                          m + pd.offsets.MonthEnd(12)].mean()
                  for m in g["open_month"]]
    print(f"{name:<19}{policy:<15}{len(g):>6,}{cells}"
          f"{np.mean(first_year):>8.1f}%")
print("jobless: average unemployment over each loan's first 12 months")
