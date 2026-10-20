# Fernhill's mortgages under the standardised approach: each loan's
# balance over the home's value when it was bought, and its weight.
import fernhill
import pandas as pd
from ballast import capital

con = fernhill.connect()
s = capital.standardised(capital.book(con), capital.provisions())
m = s[s["product"] == "mortgage"].copy()
edges = [0] + capital.LTV_EDGES + [9]
labels = ["up to 50%", "50-60%", "60-80%", "80-90%", "90-100%",
          "over 100%"]
m["band"] = pd.cut(m.ltv, edges, labels=labels)
g = m.groupby("band", observed=False).agg(
    n=("account_id", "size"), bal=("drawn_cents", "sum"),
    rwa=("sa_rwa", "sum"))
print(f"{'loan-to-value':<14}{'loans':>7}{'balance $m':>12}"
      f"{'weight':>8}{'RWA $m':>9}")
for (band, r), rw in zip(g.iterrows(), capital.LTV_RW):
    print(f"{band:<14}{int(r.n):>7,}{r.bal / 1e8:>12,.1f}{rw:>8.0%}"
          f"{r.rwa / 1e8:>9,.1f}")
bal, rwa = m.drawn_cents.sum(), m.sa_rwa.sum()
print(f"{'all':<14}{len(m):>7,}{bal / 1e8:>12,.1f}{rwa / bal:>8.1%}"
      f"{rwa / 1e8:>9,.1f}")
w = (m.ltv * m.drawn_cents).sum() / bal
print(f"\nbalance-weighted LTV {w:.1%}; in default: "
      f"{m.in_default.sum()} loans at "
      f"{capital.DEFAULTED_MORTGAGE_RW:.0%}")
flat = 0.35 * bal
print(f"one weight of 35% for every mortgage: RWA ${flat / 1e8:,.1f}m")
