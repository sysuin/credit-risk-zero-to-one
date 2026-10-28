# Card vintages computed the obvious way, one account id per card.
import pandas as pd

import fernhill
from ballast import performance as perf

AGES = (6, 12, 24, 36, 48)
con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021", stitched=False)
table = perf.vintage_table(con, "card", eps, stitched=False)
moved = dict(con.execute("""
    SELECT year(open_date)::VARCHAR, count(*) FROM accounts
    WHERE close_reason = 'migrated' GROUP BY 1""").fetchall())
print(f"{'opened':<8}{'cards':>7}" + "".join(
    f"{'m' + str(k):>7}" for k in AGES) + f"{'migrated':>10}")
for cohort, row in table.iterrows():
    cells = ""
    for age in AGES:
        if pd.isna(row[age]):  # too young to have reached this age
            cells += f"{'.':>7}"
        else:
            cells += f"{row[age]:>7.1%}"
    print(f"{cohort:<8}{int(row['accounts']):>7,}{cells}"
          f"{moved.get(cohort, 0):>10,}")
