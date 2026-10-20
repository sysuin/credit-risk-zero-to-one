# The output floor: total RWA may not fall below 72.5% of the
# standardised total. Does it bind for Fernhill, and when would it?
import json

import fernhill
from ballast import capital

con = fernhill.connect()
r = capital.load()
k = capital.bank_capital(con)
other = k["operational_rwa"] + k["market_rwa"]
sa = capital.credit_rwa(r) + other
floor = capital.OUTPUT_FLOOR * sa
print(f"standardised total RWA ${sa / 1e8:,.0f}m; floor at "
      f"{capital.OUTPUT_FLOOR:.1%}: ${floor / 1e8:,.0f}m")
cases = {"mortgages on IRB": ["mortgage"],
         "all retail on IRB": [p for p in r["product"].unique()
                               if not p.startswith("commercial")],
         "everything on IRB": list(r["product"].unique())}
print(f"\n{'':<20}{'RWA $m':>8}{'of SA':>7}{'floored $m':>12}")
bars = {"standardised": sa}
for name, prods in cases.items():
    t = capital.credit_rwa(r, prods) + other
    bars[name] = t
    print(f"{name:<20}{t / 1e8:>8,.0f}{t / sa:>7.1%}"
          f"{capital.output_floor(t, sa) / 1e8:>12,.0f}")

m = r[r["product"] == "mortgage"]
ms, mi = m.sa_rwa.sum(), m.irb_rwa.sum()
rest = sa - ms
print(f"\nmortgages alone: IRB ${mi / 1e8:,.1f}m is {mi / ms:.0%} of "
      f"SA; floored ${capital.output_floor(mi, ms) / 1e8:,.1f}m")
x = (1 - capital.OUTPUT_FLOOR) * rest / (capital.OUTPUT_FLOOR * ms - mi)
print(f"the floor binds once the mortgage book is {x:.1f} times "
      f"today's,")
print(f"  ${x * m.drawn_cents.sum() / 1e8:,.0f}m of mortgages beside "
      f"the rest of the book")
t = capital.credit_rwa(r, cases["everything on IRB"]) + other
print(f"\nthe most the floor lets IRB save: "
      f"${(sa - floor) / 1e8:,.0f}m")
print(f"what everything on IRB saves:     ${(sa - t) / 1e8:,.0f}m")
with open("code/21/15_output_floor.json", "w") as f:
    json.dump({"bars": bars, "floor": floor, "other": other}, f)
