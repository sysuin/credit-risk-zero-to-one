# timeout: 1800
# A limit from the stress test: how much watchlist exposure (grades
# 9 and 10) the supervisor's scenario lets Fernhill carry.
import fernhill
from ballast import appetite as ap
from ballast import stress

con = fernhill.connect()
cap = ap.capital_now(con)
inp = stress.inputs(con)
path = stress.paths(con)["stress_2026"]
today = stress.load()["summary"]["trough_sa"]["stress_2026"]
goals = {"appetite": cap["requirement"], "tolerance": cap["minimum"]}
found = ap.watchlist_limit(inp, path, today, goals)
print("share of today's watchlist kept -> lowest CET1 ratio,")
print("supervisor's scenario, everything else as it stands:")
for k, v in found["tried"].items():
    print(f"  {float(k):>6.3f}  {v:>7.2%}")
cb = inp["cb"]
n = ap.names(con, cap["tier1"])
now = float(n.ead[n.grade >= ap.WATCHLIST].sum())
lim = {"now": now}
for name, goal in goals.items():
    lim[name] = found[name]["share"] * now
    print(f"{name}: trough {goal:.1%} at {found[name]['share']:.1%} of "
          f"today's ${now / 1e8:,.0f}m: ${lim[name] / 1e8:,.0f}m")
lim["share"] = {k: found[k]["share"] for k in goals}
lim["tried"] = found["tried"]
print(f"saved to {ap.save_limits(lim)}")
