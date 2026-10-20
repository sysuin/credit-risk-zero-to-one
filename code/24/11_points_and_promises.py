# The card behavioural score as a points table, the lines that did not
# earn a place, and whether its promises held on the test quarters.
import datetime as dt

import pandas as pd

import fernhill
from ballast import monitoring as mon
from ballast.scorecard import metrics

con = fernhill.connect()
months = mon.quarter_ends(dt.date(2017, 12, 31), dt.date(2024, 12, 31))
f = mon.behaviour_frame(con, months, products=("card",))
dev = f[f["month"].astype(str) < "2022-01-01"]
test = f[f["month"].astype(str) >= "2022-01-01"]
card = mon.load_behaviour()["card"]
print(f"Card behavioural score: base {card.base}, then per line")
for line, bands in card.table.items():
    cells = [f"{b}:{p}" for b, p in bands.items()]
    if len(" ".join(cells)) > 50:
        print(f"  {line:<15}" + " ".join(cells[:3]))
        cells = cells[3:]
        line = ""
    print(f"  {line:<15}" + " ".join(cells))
g = metrics.gini(card.score(test), test["bad"])
print(f"Gini on the test quarters: {g:.3f}")
for extra in ("payment_ratio", "behind_12m"):
    lines = mon.PRODUCT_LINES["card"] + [extra]
    alt = mon.fit_behaviour(dev, "card", lines=lines)
    pts = " ".join(f"{b}:{p}" for b, p in alt.table[extra].items())
    g = metrics.gini(alt.score(test), test["bad"])
    print(f"  adding {extra}: Gini {g:.3f}\n    points {pts}")
s = card.score(test)
band = pd.cut(s, [0, 560, 590, 610, 630, 999], right=False,
              labels=["<560", "560-589", "590-609", "610-629", "630+"])
t = pd.DataFrame({"band": band, "bad": test["bad"],
                  "promised": card.bad_rate(test)})
print("\nTest quarters by score band")
print(f"{'band':<10}{'rows':>9}{'promised':>10}{'seen':>8}")
for b, g in t.groupby("band", observed=True):
    print(f"{b:<10}{len(g):>9,}{g.promised.mean():>10.2%}"
          f"{g.bad.mean():>8.2%}")
print(f"{'all':<10}{len(t):>9,}{t.promised.mean():>10.2%}"
      f"{t.bad.mean():>8.2%}")
