# Exercise 26.4: the rate replay started a year later, from January
# 2023, when most of the rise had already happened.
# timeout: 600
import fernhill
from ballast import stress

con = fernhill.connect()
inp = stress.inputs(con)
for first in ("2022-01-31", "2023-01-31"):
    p = stress.historical(con, first)
    r = stress.project(inp, p)
    print(f"from {first[:7]}: policy rate peaks at "
          f"{p.policy.max():.2f}%,"
          f" trough {r['trough_sa']:.1%},")
    print(f"  three-year loss ${r['years'].loss.sum() / 1e8:,.0f}m")
