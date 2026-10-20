# What the arrears figure said in 2020, and what it left out: the
# consumer book split by whether the account ever took a holiday.
import datetime as dt
import json

import fernhill
from ballast import monitoring as mon
from ballast.config import ROOT

con = fernhill.connect()
t = mon.stress_indicators(con, dt.date(2019, 1, 31),
                          dt.date(2021, 12, 31))
print("Consumer accounts open and not written off: share 30+ days")
print("behind, by whether the account took a 2020 payment holiday")
print(f"{'month':<9}{'all':>7}{'holiday':>9}{'others':>8}"
      f"{'on':>9}{'behind or':>11}{'unemp-':>8}")
print(f"{'':<9}{'':>7}{'accounts':>9}{'':>8}{'holiday':>9}"
      f"{'on holiday':>11}{'loyment':>8}")
show = t[(t.month.astype(str) >= "2020-01")
         & (t.month.astype(str) < "2021-07")]
for r in show.itertuples():
    print(f"{str(r.month)[:7]:<9}{r.dq30:>7.2%}"
          f"{r.dq30_holiday_accounts:>9.2%}{r.dq30_others:>8.2%}"
          f"{r.on_holiday:>9.1%}{r.not_paying:>11.1%}"
          f"{r.unemployment:>7.2f}%")
peak = t.loc[t.dq30.idxmax()]
dec = t[t.month.astype(str) == "2020-12-31"].iloc[0]
print(f"arrears peaked {str(peak.month)[:7]} at {peak.dq30:.2%}; "
      f"December 2020 {dec.dq30:.2%}")
cols = ["dq30", "dq30_holiday_accounts", "dq30_others", "on_holiday",
        "not_paying", "card_utilisation", "card_minimum_only",
        "enquiries_3plus", "unemployment"]
fig = {"month": [str(m)[:7] for m in t.month],
       **{c: [round(float(x), 5) for x in t[c]] for c in cols}}
(ROOT / "code" / "24" / "08_holidays.json").write_text(
    json.dumps(fig) + "\n")
