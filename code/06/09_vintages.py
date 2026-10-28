# Personal-loan vintages: the share of each year's loans in default by
# each age, under the 2021 definition applied to the whole decade, and
# the unemployment rate each vintage lived through.
import pandas as pd

import fernhill
from ballast import performance as perf

AGES = (6, 12, 24, 36, 48)
con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")
table = perf.vintage_table(con, "personal", eps)
jobless = dict(con.execute("""
    SELECT y.yr, max(m.unemployment_pct)
    FROM (SELECT DISTINCT year(month) AS yr FROM macro) y
    JOIN macro m ON m.month >= make_date(y.yr, 1, 1)
                AND m.month < make_date(y.yr + 2, 1, 1)
    GROUP BY 1""").fetchall())
print(f"{'opened':<8}{'loans':>7}" + "".join(
    f"{'m' + str(k):>7}" for k in AGES) + f"{'jobless':>9}")
for cohort, row in table.iterrows():
    cells = ""
    for age in AGES:
        if pd.isna(row[age]):  # too young to have reached this age
            cells += f"{'.':>7}"
        else:
            cells += f"{row[age]:>7.1%}"
    print(f"{cohort:<8}{int(row['accounts']):>7,}{cells}"
          f"{jobless[int(cohort)]:>8.1f}%")
print("jobless: highest unemployment in the year opened and the next")
