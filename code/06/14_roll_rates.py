# Personal loans, January 2023 to December 2025: where accounts in
# each arrears bucket were one month end later, and what the matrix
# predicts a year ahead against what happened.
import datetime as dt
import json

import fernhill
from ballast import performance as perf
from ballast.config import ROOT

con = fernhill.connect()
m = perf.transition_matrix(con, "personal", dt.date(2023, 1, 31),
                           dt.date(2025, 11, 30))
cols = [c for c in m.columns if c != "n"]
short = {"current": "cur", "paid off": "paid", "written off": "w/off"}
print(f"{'from':<9}" + "".join(f"{short.get(c, c):>6}" for c in cols)
      + f"{'months':>9}")
for b, row in m.iterrows():
    print(f"{b:<9}" + "".join(f"{row[c]:>6.1%}" for c in cols)
          + f"{int(row['n']):>9,}")
json.dump({"rows": list(m.index), "cols": cols,
           "share": m[cols].round(5).values.tolist()},
          open(ROOT / "code/06/14_roll_rates.json", "w"))

flow = perf.flow_to_loss(m)
year = perf.project(m, 12)["written off"]
seen = dict(con.execute("""
    WITH h AS (
        SELECT account_id, month, missed, status,
               min(month) FILTER (WHERE status IN ('charged_off'))
                   OVER (PARTITION BY account_id) AS off
        FROM performance WHERE product = 'personal')
    SELECT CASE WHEN missed = 0 THEN 'current'
                ELSE (missed * 30)::VARCHAR END,
           avg((off IS NOT NULL
                AND off <= last_day(month + INTERVAL 12 MONTH))::INT)
    FROM h
    WHERE month BETWEEN DATE '2023-01-31' AND DATE '2024-12-31'
      AND status IN ('up_to_date', 'arrears', 'default')
    GROUP BY 1""").fetchall())
print(f"\n{'from':<9}{'roll one':>10}{'chain':>8}{'matrix':>9}"
      f"{'actual':>9}")
print(f"{'':<9}{'bucket':>10}{'to loss':>8}{'12 mo':>9}{'12 mo':>9}")
for b, row in flow.iterrows():
    print(f"{b:<9}{row['flow']:>10.1%}{row['to_loss']:>8.2%}"
          f"{year[b]:>9.2%}{seen[b]:>9.2%}")
