# Do Fernhill's defaults cluster? Each segment's yearly default rate
# against the spread it would show if borrowers defaulted alone.
import fernhill
import numpy as np
from ballast import portfolio as pf

con = fernhill.connect()
h = pf.default_history(con)
print(f"{'segment':<14}{'years':>6}{'at risk':>9}{'rate':>7}"
      f"{'sd seen':>9}{'if alone':>10}{'ratio':>7}")
for seg in pf.SEGMENTS + ["sme_emergency"]:
    g = h[h.segment == seg]
    alone = np.sqrt(np.mean(g.rate * (1 - g.rate) / g.at_risk))
    sd = g.rate.std(ddof=1)
    print(f"{seg:<14}{len(g):>6}{g.at_risk.mean():>9,.0f}"
          f"{g.rate.mean():>7.2%}{sd:>9.2%}{alone:>10.2%}"
          f"{sd / alone:>7.1f}")
c = h[h.segment == "companies"]
print("\ncompanies' defaults by year, 2017-2025: "
      + " ".join(str(d) for d in c.defaults))
print(f"  {c.defaults.sum()} in {c.at_risk.sum():,} client-years")
