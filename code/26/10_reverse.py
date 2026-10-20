# Reverse stress testing: how far would the economy have to go for
# Fernhill's CET1 ratio to touch its requirement of 8.0%?
# timeout: 2400
import json

import fernhill
from ballast import capital, stress

con = fernhill.connect()
inp = stress.inputs(con)
paths = stress.paths(con)
s0 = inp["start"]
req = capital.requirements()["cet1"]
every = ("u", "hpi", "car", "policy")
a = stress.reverse(inp, paths["stress_2026"], lo=0.0, hi=1.0,
                   what=every)
b = stress.reverse(inp, paths["severe"], lo=1.0, hi=1.5)
print(f"CET1 trough equal to the requirement, {req:.1%}:")
for name, r in (("the supervisor's shape", a),
                ("Fernhill's severe shape", b)):
    print(f"  {name}, x {r['k']:.2f} ({len(r['steps'])} runs):")
    print(f"    unemployment peaks at {r['peak_u']:.2f}%, policy rate "
          f"at {r['peak_policy']:.2f}%,")
    print(f"    house prices {r['hpi_fall']:+.1%}, used cars "
          f"{r['car_fall']:+.1%}; trough {r['trough_sa']:.2%}")

print("\nTrough by peak unemployment and the path of rates (the")
print("supervisor's shape, its unemployment and prices scaled)")
ks = [0.0, 0.5, 1.0, 1.5]
rates = [("rates held", 0.0), ("half the rise", 0.5),
         ("full rise", 1.0)]
print(f"{'peak unemployment':<20}" + "".join(f"{n:>15}"
                                            for n, _ in rates))
grid = {n: [] for n, _ in rates}
for k in ks:
    cells, peak = [], None
    for n, kr in rates:
        p = stress.scaled(paths["stress_2026"], s0, k)
        p = stress.scaled(p, s0, kr, ("policy",))
        t = stress.project(inp, p)["trough_sa"]
        grid[n].append(t)
        cells.append(t)
        peak = p.u.max()
    print(f"{peak:>17.2f}%  " + "".join(f"{t:>15.1%}" for t in cells))

flat = stress.scaled(paths["stress_2026"], s0, 0.0, every)
houses = flat.copy()
houses["hpi"] = stress.scaled(paths["stress_2026"], s0, 0.5 / 0.29,
                              ("hpi",)).hpi
h = stress.project(inp, houses)
mort = h["products"].query("product == 'mortgage'").loss.sum()
print(f"\nhouse prices alone {houses.hpi.min() / s0['hpi'] - 1:+.0%}, "
      f"nothing else moving: trough {h['trough_sa']:.1%},")
print(f"three-year mortgage loss ${mort / 1e8:.1f}m")

print("\nHow much the supervisor's answer rests on the commercial book")
for name, kw in (("as projected", {}),
                 ("no rate effect", {"rate_beta": 0.0}),
                 ("satellite's unemployment b", "corp")):
    if kw == "corp":
        r = stress.project(inp, paths["stress_2026"],
                           corp_u=inp["corp_u_beta"])
    else:
        r = stress.project(dict(inp, **kw), paths["stress_2026"])
    print(f"  {name:<28}trough {r['trough_sa']:>6.1%}, loss "
          f"${r['years'].loss.sum() / 1e8:,.0f}m")

keys = ("k", "peak_u", "peak_policy", "hpi_fall", "car_fall",
        "trough_sa")
stress.save_reverse({"target": req,
                     "stress_2026": {k: a[k] for k in keys},
                     "severe": {k: b[k] for k in keys}})
with open("code/26/10_reverse.json", "w") as f:
    json.dump({"req": req, "peaks": [s0["u"] + k * (paths[
        "stress_2026"].u.max() - s0["u"]) for k in ks], "grid": grid,
        "supervisor": {k: a[k] for k in ("k", "peak_u", "peak_policy",
                                          "hpi_fall")},
        "severe": {k: b[k] for k in ("k", "peak_u", "peak_policy",
                                      "hpi_fall")}}, f)
