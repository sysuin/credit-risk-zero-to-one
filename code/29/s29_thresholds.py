# Exercise 29.1: how the tiers move if thin evidence means fewer than
# 100 or 150 defaults instead of 50, and if nothing inherits a tier.
import fernhill
from ballast import governance as gv

con = fernhill.connect()
runs = {}
for n in (50, 100, 150):
    gv.THIN_EVIDENCE = n
    runs[n] = {e["id"]: e for e in gv.build_inventory(con)}
base = runs[50]
print(f"{'id':<6}{'evidence':>9}{'at 50':>7}{'at 100':>8}{'at 150':>8}"
      f"{'own tier':>10}")
for k, e in base.items():
    t = [runs[n][k]["tier"] for n in runs] + [runs[50][k]["own_tier"]]
    if e["tier"] is None or len(set(t)) == 1:
        continue
    ev = "-" if e["evidence_n"] is None else f"{e['evidence_n']:,}"
    print(f"{k:<6}{ev:>9}" + "".join(f"{x:>{w}}" for x, w in
                                      zip(t, (7, 8, 8, 10))))
