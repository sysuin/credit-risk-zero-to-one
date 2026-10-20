# Exercise 27.3: the client limit at which one default costs exactly
# the one-point management buffer.
import fernhill
from ballast import appetite as ap

con = fernhill.connect()
cap = ap.capital_now(con)
own = ap.pf.commercial_lgd(con)
budget = ap.BUFFER * cap["sa_rwa"]
print(f"one point of CET1: ${budget / 1e8:,.1f}m")
for secured, label in ((True, "secured"), (False, "unsecured")):
    ead = budget / own[secured]
    print(f"{label:<10} LGD {own[secured]:.1%}: "
          f"EAD ${ead / 1e8:,.1f}m, "
          f"{ead / cap['tier1']:.1%} of Tier 1")
