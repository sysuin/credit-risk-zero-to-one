# Working capital: how long Meridian's money sits in stock and with
# its customers, how long its suppliers wait, and what the change
# in those days cost in cash.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
r = sp.ratios(s)
print(f"{'days':<28}" + "".join(f"{y:>9}" for y in s.columns))
for key, label in [("inventory_days", "inventory days"),
                   ("receivable_days", "+ receivable days"),
                   ("payable_days", "- trade payable days"),
                   ("cash_cycle", "= cash conversion cycle")]:
    print(f"{label:<28}" + "".join(f"{v:>9.1f}" for v in r.loc[key]))

nwc = s.loc["receivables"] + s.loc["inventory"] - s.loc["payables"]
print(f"\n{'working capital, $000':<28}"
      + "".join(f"{v / 1e5:>9,.0f}" for v in nwc))
print(f"{'  as a share of revenue':<28}"
      + "".join(f"{v:>9.1%}" for v in nwc / s.loc["revenue"]))

rev, recv = s.loc["revenue", 2025], s.loc["receivables", 2025]
at48 = rev * r.loc["receivable_days", 2022] / sp.DAYS
print(f"\n2025 receivables at 2022's "
      f"{r.loc['receivable_days', 2022]:.0f} days: "
      f"${at48 / 1e8:,.1f}m, not ${recv / 1e8:,.1f}m")
print(f"  cash tied up by the extra days: ${(recv - at48) / 1e8:,.1f}m")
print(f"  one day of 2025 sales: ${rev / sp.DAYS / 100:,.0f}")

json.dump({"years": list(s.columns),
           **{k: [round(float(v), 2) for v in r.loc[k]]
              for k in ["inventory_days", "receivable_days",
                        "payable_days", "cash_cycle"]}},
          open(ROOT / "code/14/09_working_capital.json", "w"))
