# Exercise 24.3: the behavioural score on 31 March 2020, before any
# holiday, and what happened by March 2021 to those who took one.
import datetime as dt

import pandas as pd

import fernhill
from ballast import monitoring as mon

con = fernhill.connect()
f = mon.behaviour_frame(con, [dt.date(2020, 3, 31)])
scores = mon.load_behaviour()
f["score"] = 0
for p, b in scores.items():
    m = f["product"].eq(p)
    f.loc[m, "score"] = b.score(f[m])
took = con.execute("""SELECT DISTINCT account_id FROM account_events
                      WHERE event = 'payment_holiday_start'""").df()
f["holiday"] = f["account_id"].isin(took["account_id"])
f["band"] = pd.cut(f["score"], [0, 560, 590, 610, 999], right=False,
                   labels=["<560", "560-589", "590-609", "610+"])
print("personal loans and cards up to date or nearly, 31 March 2020")
print(f"{'band':<9}{'holiday':>9}{'bad 12m':>9}{'no holiday':>12}"
      f"{'bad 12m':>9}")
for b, g in f.groupby("band", observed=True):
    h, n = g[g.holiday], g[~g.holiday]
    print(f"{b:<9}{len(h):>9,}{h.bad.mean():>9.1%}{len(n):>12,}"
          f"{n.bad.mean():>9.1%}")
print(f"share taking a holiday: {f.holiday.mean():.1%}; mean score "
      f"{f[f.holiday].score.mean():.0f} against "
      f"{f[~f.holiday].score.mean():.0f}")
