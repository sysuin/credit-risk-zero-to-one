# Both definitions of default recomputed from the monthly rows over the
# whole decade, checked against what Fernhill's systems recorded.
import json

import pandas as pd

import fernhill
from ballast import performance as perf
from ballast.config import ROOT

con = fernhill.connect()
old = perf.default_episodes(con, "dpd90", stitched=False)
new = perf.default_episodes(con, "dod2021", stitched=False)
rec = con.execute("SELECT account_id, default_month, definition "
                  "FROM defaults ORDER BY ALL").df()
rec["default_month"] = rec["default_month"].dt.date


def keys(df, lo, hi):
    m = pd.to_datetime(df["default_month"]).dt.year
    df = df[(m >= lo) & (m <= hi)]
    return set(zip(df["account_id"], df["default_month"]))


for name, eps, lo, hi in [("dpd90", old, 2016, 2020),
                          ("dod2021", new, 2021, 2025)]:
    ours = keys(eps, lo, hi)
    theirs = keys(rec[rec["definition"] == name], lo, hi)
    print(f"{name} {lo}-{hi}: recomputed {len(ours):,}, recorded "
          f"{len(theirs):,}, in both {len(ours & theirs):,}")
    if ours != theirs:
        late = sorted(ours - theirs)
        early = sorted(theirs - ours)
        print(f"  only recomputed: {len(late)}, all in "
              f"{sorted({str(m)[:7] for _, m in late})}")
        print(f"  only recorded:   {len(early)}, all in "
              f"{sorted({str(m)[:7] for _, m in early})}")
        held = con.execute("""
            SELECT count(DISTINCT account_id) FROM defaults
            WHERE definition = 'dpd90' AND (cure_month IS NULL
                   OR cure_month > DATE '2020-12-31')
              AND account_id IN (SELECT unnest(?))""",
                           [[a for a, _ in late]]).fetchone()[0]
        bankrupt = con.execute("""
            SELECT count(DISTINCT account_id) FROM account_events
            WHERE event = 'bankruptcy' AND year(event_date) = 2020
              AND account_id IN (SELECT unnest(?))""",
                               [[a for a, _ in early]]).fetchone()[0]
        print(f"  recomputed-only still in a 2020 default: {held}")
        print(f"  recorded-only made bankrupt in 2020:     {bankrupt}")

open_jan = dict(con.execute("""
    SELECT year(month) + 1, count(*) FROM performance
    WHERE month(month) = 12
      AND status IN ('up_to_date', 'arrears', 'default')
    GROUP BY 1""").fetchall())
# Defaults per year in each of the three series.
year = {}
for name, eps in [("recorded", rec), ("dpd90", old), ("dod2021", new)]:
    year[name] = pd.to_datetime(eps["default_month"]).dt.year \
        .value_counts()
print(f"{'year':<6}{'open 1 Jan':>11}{'recorded':>14}{'dpd90':>14}"
      f"{'dod2021':>14}")
series = []
for y in range(2017, 2026):
    cells = [year[n][y] for n in ("recorded", "dpd90", "dod2021")]
    line = f"{y:<6}{open_jan[y]:>11,}"
    for c in cells:
        line += f"{c:>7}{c / open_jan[y]:>7.2%}"
    print(line)
    series.append({"year": y, "open": open_jan[y],
                   "recorded": int(cells[0]), "dpd90": int(cells[1]),
                   "dod2021": int(cells[2])})
json.dump(series, open(ROOT / "code/06/04_recompute.json", "w"))
