# Exercise 3: the engine on 31 December 2021 against 2022's defaults,
# as listing 15 did for 2023 and 2024.
# timeout: 300
import datetime as dt

import fernhill
import pandas as pd
from ballast import ecl
from ballast import performance as perf

DATE = dt.date(2021, 12, 31)
con = fernhill.connect()
r = ecl.run(con, DATE, ecl.parameters(con, DATE))
ok = r[(r["stage"] < 3) & (r["segment"] == "retail")]
eps = perf.default_episodes(con)
d22 = set(eps["account_id"][pd.to_datetime(eps["default_month"])
                            .dt.year == 2022])
ok = ok.assign(y=ok["root_id"].isin(d22))
print(f"{'retail, 31 Dec 2021':<20}{'accounts':>9}{'expected':>10}"
      f"{'actual':>8}")
for p, g in ok.groupby("product"):
    print(f"{p:<20}{len(g):>9,}{g['pd12'].sum():>10.0f}"
          f"{g['y'].sum():>8,}")
print(f"{'all':<20}{len(ok):>9,}{ok['pd12'].sum():>10.0f}"
      f"{ok['y'].sum():>8,}")
