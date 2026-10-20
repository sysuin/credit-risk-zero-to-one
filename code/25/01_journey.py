# Fernhill's collections ladder as its records show it in 2025, and
# where consumer accounts that fell behind in 2022-2023 got to.
import json

import fernhill
from ballast import collections as coll
from ballast import performance as perf
from ballast.config import ROOT

con = fernhill.connect()
perf.prepare(con)
acts = con.execute("""
    SELECT CASE WHEN p.missed >= 5 THEN 5 ELSE p.missed END AS rung,
           c.action, count(*) AS n, count(DISTINCT c.account_id) AS a
    FROM collections c JOIN performance p
      ON p.account_id = c.account_id AND p.month = c.month
    WHERE c.month BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
    GROUP BY ALL ORDER BY rung, n DESC""").fetchall()
print("2025: actions by payments missed")
print(f"{'missed':<7}{'action':<16}{'actions':>8}{'accounts':>9}"
      "  ladder says")
for rung, action, n, a in acts:
    label = f"{rung}+" if rung == 5 else str(rung)
    print(f"{label:<7}{action:<16}{n:>8,}{a:>9,}"
          f"  {coll.ladder_action(rung)}")

e = coll.entries(con, "2022-01-01", "2023-12-31")
con.register("e", e[["root_id", "month"]].assign(
    month=e["month"].dt.date))
far = con.execute(f"""
    SELECT e.root_id, e.month, max(h.missed) AS worst,
      max(CASE WHEN h.status IN {perf.WRITTEN_OFF} THEN 1 ELSE 0 END)
          AS off,
      arg_max(h.status, h.month) AS last_status,
      arg_max(h.missed, h.month) AS last_missed
    FROM e JOIN history h ON h.root_id = e.root_id
     AND h.month BETWEEN e.month
         AND last_day(e.month + INTERVAL 12 MONTH)
    GROUP BY 1, 2""").df()
n = len(far)
print(f"\nConsumer accounts falling behind, 2022-2023: {n:,} entries")
print("got as far as, within 12 months:")
rungs = {}
for k, name in [(2, "60 days"), (3, "90 days"),
                (4, "120 days"), (5, "150 days")]:
    share = (far["worst"] >= k).mean()
    rungs[name] = share
    print(f"  {name:<10}{share:>7.1%}")
off = far["off"].mean()
rungs["written off"] = off
rungs["entries"] = n
print(f"  {'written off (charged off or car taken)':<38}{off:>6.1%}")
up = (far["last_missed"].eq(0) & far["off"].eq(0)).mean()
print(f"a year on: up to date or repaid {up:.1%}, still behind "
      f"{1 - up - off:.1%}")
json.dump(rungs, open(ROOT / "code/25/01_journey.json", "w"),
          indent=1)
