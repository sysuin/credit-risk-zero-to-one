# Six regions, one economy: consumer default rates by region and year,
# and how closely each region's years moved with the others'.
import json

import numpy as np

import fernhill
from ballast import performance as perf
from ballast.config import ROOT

con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021")      # prepares `history`
con.register("eps", eps[["account_id", "default_month",
                         "cure_month"]])
t = con.execute(f"""
    WITH years AS (SELECT unnest(range(2017, 2026)) AS year),
    open_ AS (
        SELECT y.year, h.root_id, a.region
        FROM years y
        JOIN history h ON h.month = make_date(y.year - 1, 12, 31)
        JOIN accounts a ON a.account_id = h.root_id
        WHERE h.product IN ('personal', 'card', 'auto', 'mortgage')
          AND h.status IN {perf.OPEN}
          AND NOT EXISTS (
              SELECT 1 FROM eps e WHERE e.account_id = h.root_id
                AND e.default_month <= h.month
                AND (e.cure_month IS NULL OR e.cure_month > h.month)))
    SELECT o.year, o.region, count(DISTINCT o.root_id) AS at_risk,
           count(DISTINCT e.account_id) AS defaults
    FROM open_ o LEFT JOIN eps e ON e.account_id = o.root_id
     AND year(e.default_month) = o.year
    GROUP BY ALL ORDER BY ALL""").df()
t["rate"] = t["defaults"] / t["at_risk"]
w = t.pivot(index="year", columns="region", values="rate")
print("Consumer default rate by region and year, % (2021 definition)")
print(f"{'':<12}" + "".join(f"{y:>6}" for y in w.index))
for r in w.columns:
    print(f"{r:<12}" + "".join(f"{v * 100:>6.2f}" for v in w[r]))
corr = w.corr().to_numpy()[np.triu_indices(len(w.columns), 1)]
worst = w.idxmax()
print(f"worst year in every region: "
      f"{', '.join(sorted(set(map(str, worst))))}")
print(f"2020 over the region's 2019: "
      f"{(w.loc[2020] / w.loc[2019]).min():.2f}x to "
      f"{(w.loc[2020] / w.loc[2019]).max():.2f}x")
print(f"correlation of regions' yearly rates, 15 pairs: "
      f"{corr.min():.2f} to {corr.max():.2f}")
(ROOT / "code" / "30" / "04_one_economy.json").write_text(json.dumps({
    "year": [int(y) for y in w.index],
    "regions": {r: [round(float(v), 5) for v in w[r]]
                for r in w.columns}}) + "\n")
