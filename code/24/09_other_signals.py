# The signals a payment holiday cannot freeze: each one in 2020-21
# against its own range over 2019.
import datetime as dt

import fernhill
from ballast import monitoring as mon

con = fernhill.connect()
t = mon.stress_indicators(con, dt.date(2019, 1, 31),
                          dt.date(2021, 6, 30))
t["month"] = t["month"].astype(str).str[:7]
base = t[t["month"] < "2020-01"]
SIGNALS = {"dq30": ("30+ days behind", "{:.2%}"),
           "not_paying": ("behind or on holiday", "{:.1%}"),
           "holiday_requests": ("holiday requests", "{:,.0f}"),
           "card_utilisation": ("card utilisation", "{:.1%}"),
           "card_minimum_only": ("cards paying minimum", "{:.1%}"),
           "enquiries_3plus": ("3+ enquiries", "{:.1%}"),
           "applications": ("applications", "{:,.0f}")}
print("Each signal against 2019: mean, and from 2020 the first month")
print("it left mean +/- 3 sd of 2019's months, December 2020, and")
print("its furthest value (enquiries: share of applicants with 3+)")
print(f"{'signal':<21}{'2019':>7}{'first':>9}{'Dec 2020':>9}"
      f"{'furthest':>10}{'when':>9}")
for col, (name, f) in SIGNALS.items():
    m, sd = base[col].mean(), base[col].std()
    after = t[t["month"] >= "2020-01"]
    out = after[(after[col] - m).abs() > 3 * max(sd, 1e-9)]
    first = out["month"].iloc[0] if len(out) else "never"
    far = after.loc[(after[col] - m).abs().idxmax()]
    dec = after.loc[after["month"] == "2020-12", col].iloc[0]
    print(f"{name:<21}{f.format(m):>7}{first:>9}{f.format(dec):>9}"
          f"{f.format(far[col]):>10}{far['month']:>9}")
u = t.set_index("month")["unemployment"]
print(f"unemployment: {u['2019-12']:.2f}% in Dec 2019, "
      f"{u['2020-04']:.2f}% in Apr 2020")
