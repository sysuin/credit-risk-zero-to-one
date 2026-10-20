# Exercise 4: the personal-loan transition matrix through the holiday
# year, beside 2023-2025.
import datetime as dt

import fernhill
from ballast import performance as perf

con = fernhill.connect()
periods = {"Apr 2020-Mar 2021": (dt.date(2020, 4, 30),
                                 dt.date(2021, 3, 31)),
           "2023-2025": (dt.date(2023, 1, 31), dt.date(2025, 11, 30))}
for name, (lo, hi) in periods.items():
    m = perf.transition_matrix(con, "personal", lo, hi)
    cols = [c for c in m.columns if c != "n"]
    print(f"\n{name}")
    short = {"current": "cur", "paid off": "paid",
             "written off": "w/off"}
    print(f"{'from':<9}" + "".join(f"{short.get(c, c):>7}"
                                   for c in cols))
    for b, row in m.iterrows():
        print(f"{b:<9}" + "".join(f"{row[c]:>7.1%}" for c in cols))
