# Exercise 26.3: the supervisor's unemployment and prices with
# Fernhill's severe path of rates. How much of the gap is the rates?
# timeout: 600
import fernhill
from ballast import stress

con = fernhill.connect()
inp = stress.inputs(con)
paths = stress.paths(con)
mixed = paths["stress_2026"].copy()
mixed["policy"] = paths["severe"].policy.to_numpy()
print(f"{'scenario':<34}{'trough':>8}{'3-year loss $m':>16}")
for name, p in (("severe", paths["severe"]),
                ("supervisor's, with severe's rates", mixed),
                ("stress_2026", paths["stress_2026"])):
    r = stress.project(inp, p)
    print(f"{name:<34}{r['trough_sa']:>8.1%}"
          f"{r['years'].loss.sum() / 1e8:>16,.0f}")
