# Exercise 26.1: which assumption moves the supervisor's trough more,
# the cost of running Fernhill or the commercial rate coefficient?
# timeout: 1200
import fernhill
from ballast import stress

con = fernhill.connect()
inp = stress.inputs(con)
path = stress.paths(con)["stress_2026"]
fit = stress.fit_satellite(stress.default_history(con), "commercial",
                           ("u", "policy"))
b, se = fit["params"]["policy"], fit["bse"]["policy"]
print(f"{'case':<30}{'trough':>8}{'3-year loss $m':>16}")
central = stress.project(inp, path)
print(f"{'as in the chapter':<30}{central['trough_sa']:>8.1%}"
      f"{central['years'].loss.sum() / 1e8:>16,.0f}")
keep = stress.COST_SHARE
for share in (0.4, 0.6):
    stress.COST_SHARE = share
    r = stress.project(inp, path)
    print(f"{f'costs {share:.0%} of NII':<30}{r['trough_sa']:>8.1%}"
          f"{r['years'].loss.sum() / 1e8:>16,.0f}")
stress.COST_SHARE = keep
for name, beta in (("rate b - 1 se", b - se),
                   ("rate b + 1 se", b + se)):
    r = stress.project(dict(inp, rate_beta=beta), path)
    print(f"{f'{name} ({beta:.3f})':<30}{r['trough_sa']:>8.1%}"
          f"{r['years'].loss.sum() / 1e8:>16,.0f}")
