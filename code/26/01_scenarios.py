# The five scenarios published for 31 December 2025, year by year,
# beside the worst that Fernhill's own decade saw.
import json

import fernhill
from ballast import stress

con = fernhill.connect()
paths = stress.paths(con)
s0 = stress.start(con)
weight = dict(con.execute("""SELECT scenario, any_value(weight)
                             FROM scenarios GROUP BY 1""").fetchall())
order = ["upside", "base", "downside", "severe", "stress_2026"]
print(f"31 Dec 2025: unemployment {s0['u']:.2f}%, policy rate "
      f"{s0['policy']:.2f}%")
print("\nUnemployment, % (yearly average; peak month to 2030)")
print(f"{'scenario':<12}{'weight':>7}{'2026':>7}{'2027':>7}"
      f"{'2028':>7}{'peak':>7}")
for k in order:
    a = stress.annual(paths[k])
    w = f"{weight[k]:.0%}" if weight[k] else "none"
    print(f"{k:<12}{w:>7}" + "".join(f"{v:>7.2f}" for v in a.u)
          + f"{paths[k].u.max():>7.2f}")
print("\nPolicy rate and prices (lowest index against Dec 2025)")
print(f"{'scenario':<12}{'rate 2027':>10}{'rate peak':>10}"
      f"{'houses':>9}{'cars':>8}{'GDP low':>9}")
for k in order:
    p = paths[k]
    a = stress.annual(p)
    print(f"{k:<12}{a.policy[2027]:>9.2f}%{p.policy.max():>9.2f}%"
          f"{p.hpi.min() / s0['hpi'] - 1:>+9.1%}"
          f"{p.car.min() / s0['car'] - 1:>+8.1%}{p.gdp.min():>8.1f}%")

h = stress.history(con)
fall = lambda s: (s / s.cummax() - 1).min()          # noqa: E731
a = h.groupby(h.month.dt.year).u.mean()
print("\nThe decade, 2016-2025: unemployment peaked at "
      f"{h.u.max():.2f}%"
      f" ({h.month[h.u.idxmax()]:%b %Y}),")
print(f"highest yearly average {a.max():.2f}% ({a.idxmax()}); policy "
      f"rate at most {h.policy.max():.2f}%;")
print(f"worst fall in house prices {-fall(h.hpi):.1%}, in used cars "
      f"{-fall(h.car):.1%}")

out = {"history": {"month": list(h.month.dt.strftime("%Y-%m")),
                   **{c: list(h[c]) for c in ("u", "policy", "hpi")}},
       "paths": {k: {c: list(paths[k][c].round(3))
                     for c in ("u", "policy", "hpi")}
                 for k in ("base", "severe", "stress_2026")}}
with open("code/26/01_scenarios.json", "w") as f:
    json.dump(out, f)
