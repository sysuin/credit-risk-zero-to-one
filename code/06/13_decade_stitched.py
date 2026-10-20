# The decade on one footing: both definitions recomputed with every
# migrated card followed under its new number, beside the defaults
# table as recorded.
import pandas as pd

import fernhill
from ballast import performance as perf

con = fernhill.connect()
perf.prepare(con)
open_jan = dict(con.execute("""
    SELECT year(month) + 1, count(DISTINCT root_id) FROM history
    WHERE month(month) = 12
      AND status IN ('up_to_date', 'arrears', 'default')
    GROUP BY 1""").fetchall())
rec = con.execute("SELECT default_month FROM defaults").df()
count = {"recorded": pd.to_datetime(rec["default_month"])
         .dt.year.value_counts()}
for d in perf.DEFINITIONS:
    eps = perf.default_episodes(con, d, stitched=True)
    count[d] = pd.to_datetime(eps["default_month"]).dt.year \
        .value_counts()
print(f"{'year':<6}{'open 1 Jan':>11}{'recorded':>14}{'dpd90':>14}"
      f"{'dod2021':>14}")
for y in range(2019, 2026):
    cells = [count[n][y] for n in ("recorded", "dpd90", "dod2021")]
    print(f"{y:<6}{open_jan[y]:>11,}" + "".join(
        f"{c:>7}{c / open_jan[y]:>7.2%}" for c in cells))
