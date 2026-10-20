# Exercise 12.1: how far the floor moves with each assumption, for the
# lowest and highest of the 2026 tiers' typical borrowers.
import sys

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import book_rates, market, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
fd, fp, lgd = book_rates(con, a)
m, base = market(con), pricing.Costs(lgd=lgd)
dec = a[a["decision"].eq("approve")
        & a["app_date"].between("2025-01-01", "2025-12-31")]
tiers = {"550-564": (550, 564, 17.65), "610+": (610, 652, 10.75)}
cases = [("as assumed", {}), ("running 1.5%", {"opex_pct": 1.5}),
         ("running 3.5%", {"opex_pct": 3.5}),
         ("capital 8%", {"capital_pct": 8.0}),
         ("capital 12%", {"capital_pct": 12.0}),
         ("hurdle 12%", {"hurdle_pct": 12.0}),
         ("hurdle 18%", {"hurdle_pct": 18.0})]
print(f"{'floor of a $12,000, 36-month loan':<34}"
      + "".join(f"{k:>10}" for k in tiers))
for name, change in cases:
    c = pricing.with_costs(base, **change)
    row = []
    for lo, hi, _ in tiers.values():
        g = dec[dec["m2r"].between(lo, hi)]
        s = g["m2r"].mean()
        pd_, pp = float(fd.annual(s)), float(fp.annual(s))
        row.append(pricing.floor_rate(1_200_000, 36, pd_, pp, m, c))
    print(f"  {name:<32}" + "".join(f"{r:>10.2f}" for r in row))
print("  2026 grid price                 "
      + "".join(f"{t[2]:>10.2f}" for t in tiers.values()))
