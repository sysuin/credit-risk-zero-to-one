# Emergency business loans owed nothing for twelve months. Measured
# from opening their first year looks perfect; measured from the first
# payment due, it does not.
import pandas as pd

import fernhill
from ballast import performance as perf

con = fernhill.connect()
perf.prepare(con)
lo, hi = con.execute("""
    SELECT min(m), max(m)
    FROM (SELECT datediff('month', any_value(open_date),
                          any_value(first_due)) AS m
          FROM history WHERE product = 'sme_emergency'
          GROUP BY account_id)""").fetchone()
print(f"first payment due in month on book {lo} (latest {hi})")
eps = perf.default_episodes(con, "dod2021")
for clock in ("open", "due"):
    t = perf.vintage_table(con, "sme_emergency", eps, clock=clock)
    print(f"\nclock from {clock}: cumulative default rate")
    print(f"{'cohort':<8}{'loans':>7}" + "".join(
        f"{'m' + str(k):>8}" for k in (6, 12, 18, 24, 36)))
    for cohort, row in t.iterrows():
        cells = ""
        for age in (6, 12, 18, 24, 36):
            if pd.isna(row[age]):  # too young to have reached it
                cells += f"{'':>8}"
            else:
                cells += f"{row[age]:>8.1%}"
        print(f"{cohort:<8}{int(row['accounts']):>7,}{cells}")
