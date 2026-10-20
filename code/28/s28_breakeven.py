# timeout: 600
# Exercise 28.3: break-even multiples in the downside scenario, beside
# the base and severe ones of listing 07.
import fernhill
from ballast import securitisation as sec

con = fernhill.connect()
deal = sec.inputs(con)
print(f"{'class':<8}" + "".join(f"{s:>10}" for s in
                                ("base", "downside", "severe")))
for n in ("C", "B", "A"):
    ks = [sec.breakeven(deal, n, s) for s in
          ("base", "downside", "severe")]
    print(f"{n:<8}" + "".join(f"{k:>10.1f}" for k in ks))
