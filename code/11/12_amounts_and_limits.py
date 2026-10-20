# How much Fernhill lends once it has said yes: the personal-loan
# amount rule, and the card limit grid with how each band behaved.
import json

import numpy as np
import pandas as pd

import fernhill
from ballast import data
from ballast.config import ROOT
from ballast.decision import policy as pol

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")
        & raw["decision"].astype(str).eq("approve")].copy()
limits = np.array([pol.period_of(d)[2] for d in p["app_date"]])
p["dti"] = pol.dti_at_decision(p)
rule = pol.offered_amount(p["amount_requested_cents"], p["dti"], limits)
cut = p["offered_amount_cents"] < p["amount_requested_cents"]
same = np.mean(rule == p["offered_amount_cents"])
print(f"Personal approvals: {len(p):,}; offered less than asked "
      f"{int(cut.sum()):,};\n  amount rule reproduces {same:.1%}")

c = raw[raw["product"].astype(str).eq("card")
        & raw["decision"].astype(str).eq("approve")].copy()
grid = pol.card_limit(c["stated_income_cents"], c["mark1_score"])
print(f"Card approvals: {len(c):,}; limit grid reproduces "
      f"{np.mean(grid == c['offered_amount_cents']):.1%}")

BANDS = ["under 620", "620-659", "660 and over"]
INCOMES = [20_000, 40_000, 60_000, 100_000, 150_000]
print("\nThe card limit grid: opening limit by Mark I score and income")
print(f"  {'income':>10}" + "".join(f"{b:>15}" for b in BANDS))
cells = []
for inc in INCOMES:
    row = pol.card_limit([inc * 100] * 3, [600, 640, 680]) / 100
    cells.append(row.tolist())
    print(f"  {'$' + format(inc, ','):>10}"
          + "".join(f"{'$' + format(int(v), ','):>15}" for v in row))

out = con.execute("""
    WITH first AS (
        SELECT a.app_id, p.account_id,
               max(p.missed) FILTER (WHERE datediff('month',
                   a.open_date, p.month) BETWEEN 1 AND 12) AS worst,
               any_value(p.balance_cents * 1.0 / p.limit_cents)
                   FILTER (WHERE datediff('month', a.open_date,
                                          p.month) = 12) AS use12
        FROM accounts a JOIN performance p USING (account_id)
        WHERE a.product = 'card' AND a.open_date < DATE '2021-01-01'
        GROUP BY ALL)
    SELECT * FROM first ORDER BY app_id""").df()
c = c.merge(out, on="app_id")
c["band"] = pd.cut(c["mark1_score"], [0, 620, 660, 999], right=False,
                   labels=BANDS)
print("\nCards opened 2016-2020, by score band")
print(f"  {'band':<14}{'cards':>7}{'median limit':>14}"
      f"{'used at 12m':>13}{'90+ by 12m':>12}")
stats = []
for b, g in c.groupby("band", observed=True):
    lim = g["offered_amount_cents"].median() / 100
    print(f"  {b:<14}{len(g):>7,}{'$' + format(int(lim), ','):>14}"
          f"{g['use12'].median():>13.0%}"
          f"{(g['worst'] >= 3).mean():>12.1%}")
    stats.append({"band": b, "cards": len(g), "limit": lim,
                  "use12": round(float(g["use12"].median()), 4),
                  "bad": round(float((g["worst"] >= 3).mean()), 4)})
(ROOT / "code" / "11" / "12_amounts_and_limits.json").write_text(
    json.dumps({"bands": BANDS, "incomes": INCOMES, "grid": cells,
                "stats": stats}, indent=1) + "\n")
