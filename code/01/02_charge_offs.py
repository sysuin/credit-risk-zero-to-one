# Personal-loan charge-offs by year, and the book behind them.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

rows = con.execute("""
    WITH yearly AS (
        SELECT year(month) AS yr,
               sum(balance_cents) FILTER (
                   WHERE status = 'charged_off')         AS lost,
               count(*) FILTER (WHERE status = 'charged_off') AS n
        FROM performance
        WHERE product = 'personal'
        GROUP BY yr
    ),
    book AS (                       -- the balance owed each December
        SELECT year(month) + 1 AS yr, sum(balance_cents) AS owed
        FROM performance
        WHERE product = 'personal' AND month(month) = 12
          AND status IN ('up_to_date', 'arrears', 'default')
        GROUP BY yr
    )
    SELECT y.yr, y.n, y.lost, b.owed
    FROM yearly y JOIN book b USING (yr)
    WHERE y.yr BETWEEN 2021 AND 2025
    ORDER BY y.yr
""").fetchall()

print(f"{'year':<6}{'accounts':>9}{'charged off':>14}"
      f"{'book at 1 Jan':>16}{'rate':>7}")
for yr, n, lost, owed in rows:
    print(f"{yr:<6}{n:>9}{lost / 100:>14,.0f}"
          f"{owed / 100:>16,.0f}{lost / owed:>7.1%}")

json.dump([{"year": y, "lost": lost, "owed": owed}
           for y, _, lost, owed in rows],
          open(ROOT / "code/01/02_charge_offs.json", "w"))
