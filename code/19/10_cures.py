# The shape of LGD, and what cures do to it: counted as workouts that
# lost (almost) nothing, or left out.
import json

import numpy as np

import fernhill
from ballast.config import ROOT
from ballast.parameters import lgd

con = fernhill.connect()


def finished(definition):
    """Workouts that began 2016-2021, with their LGDs."""
    w = lgd.workouts(con, definition)
    f = lgd.cash_flows(con, w)
    w = lgd.realised(w, f, lgd.discount_rates(con, w))
    return w[(w["default_month"] <= "2021-12-31")
             & w["lgd"].notna()]


w = finished("dod2021")
EDGES = [0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, np.inf]
groups = {"unsecured": ["card", "personal", "sme_overdraft"],
          "secured": ["auto", "mortgage", "sme_term"]}
print("workouts by LGD, % of each group")
print(f"{'':<11}" + "".join(f"{f'<{e:.0%}':>8}" for e in EDGES[1:-1])
      + f"{'95%+':>8}")
hist = {}
for name, ps in groups.items():
    x = w.loc[w["product"].isin(ps), "lgd"]
    n, _ = np.histogram(x, EDGES)
    hist[name] = (n / n.sum()).tolist()
    print(f"{name:<11}" + "".join(f"{v / n.sum():>8.0%}" for v in n))

print(f"\n{'product':<15}{'cured':>7}{'without':>9}{'with':>8}"
      f"{'bankrupt':>10}{'cured':>7}")
for p, g in w.groupby("product"):
    c = g["outcome"] == "cured"
    rest = lgd.pooled(g[~c], by="product")["lgd"].iloc[0]
    both = lgd.pooled(g, by="product")["lgd"].iloc[0]
    b = g[g["trigger"] == "bankruptcy"]
    print(f"{p:<15}{c.mean():>7.0%}{rest:>9.1%}{both:>8.1%}"
          f"{len(b):>10}{(b['outcome'] == 'cured').mean():>7.0%}")
print("without / with: LGD with cures left out, and counted as zero;")
print("bankrupt: workouts a bankruptcy started, and the share cured")

old = finished("dpd90")
print(f"\n{'':<10}{'definition':<11}{'workouts':>9}{'cured':>7}"
      f"{'LGD':>7}")
for p in ("card", "personal"):
    for name, d in (("dpd90", old), ("dod2021", w)):
        g = d[d["product"] == p]
        print(f"{p:<10}{name:<11}{len(g):>9,}"
              f"{(g['outcome'] == 'cured').mean():>7.0%}"
              f"{lgd.pooled(g)['lgd'].iloc[0]:>7.1%}")
json.dump({"edges": EDGES[:-1], "hist": hist},
          open(ROOT / "code/19/10_cures.json", "w"))
