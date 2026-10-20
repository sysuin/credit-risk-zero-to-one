# timeout: 900
# Exercise 27.4: the 2026 plan with half of each grade's repricing.
import fernhill
from ballast import appetite as ap
from ballast import stress

con = fernhill.connect()
cap = ap.capital_now(con)
inp = stress.inputs(con)
plan = ap.load()["plan"]
half = {int(k): v / 2 for k, v in plan["gap_bps"].items()}
label, d, h, p = ap.plan_steps(inp, cap["tier1"], half)[3]
r = stress.project(ap.reshape(inp, d, h, p),
                   stress.paths(con)["stress_2026"])
full = plan["steps"][3]["trough"]
before = plan["steps"][2]["trough"]
print("supervisor's trough:")
print(f"  before repricing {before:.1%}, "
      f"half the increase {r['trough_sa']:.1%}, all of it {full:.1%}")
