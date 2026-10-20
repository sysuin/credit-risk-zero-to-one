# Exercise 1: the arrears ladder at the end of 2020 beside the end of
# 2025, as shares of open consumer accounts.
import datetime as dt

import fernhill

con = fernhill.connect()
names = ["current", "30", "60", "90", "120", "150", "180+"]
share = {}
for day in (dt.date(2020, 12, 31), dt.date(2025, 12, 31)):
    rows = con.execute("""
        SELECT least(missed, 6), count(*) FROM performance
        WHERE month = ? AND status IN ('up_to_date', 'arrears',
                                       'default')
          AND product IN ('personal', 'card', 'auto', 'mortgage')
        GROUP BY 1 ORDER BY 1""", [day]).fetchall()
    total = sum(n for _, n in rows)
    share[day.year] = {r: n / total for r, n in rows}
    share[day.year]["n"] = total
print(f"{'days past due':<15}{'Dec 2020':>10}{'Dec 2025':>10}")
for r, name in enumerate(names):
    print(f"{name:<15}{share[2020].get(r, 0):>10.2%}"
          f"{share[2025].get(r, 0):>10.2%}")
for y in (2020, 2025):
    behind = 1 - share[y][0]
    print(f"{y}: {share[y]['n']:,} open, {behind:.2%} 30+ dpd")
