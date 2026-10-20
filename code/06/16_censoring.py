# Young books look good: the share of each year's personal loans that
# has ever defaulted, against the share in default by the same age.
import numpy as np

import fernhill
from ballast import performance as perf
from ballast.config import AS_OF

con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")
acc = perf.cohort_accounts(con, "personal", eps)
table = perf.vintage_table(con, "personal", eps)
acc["year"] = acc["open_month"].dt.year
acc["age"] = ((AS_OF.year - acc["open_month"].dt.year) * 12
              + AS_OF.month - acc["open_month"].dt.month)
print(f"{'opened':<8}{'median age':>11}{'ever defaulted':>16}"
      f"{'by month 12':>13}")
for y, g in acc.groupby("year"):
    ever = g["default_mob"].notna().mean()
    m12 = table.loc[str(y), 12]
    m12 = f"{m12:>13.2%}" if m12 == m12 else f"{'not yet':>13}"
    print(f"{y:<8}{np.median(g['age']):>9.0f} m{ever:>16.2%}{m12}")
