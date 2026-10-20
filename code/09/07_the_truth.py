# The truth about the unknowns: how they would have done, by Mark II.
import json

import numpy as np

from _truth import applicants_with_truth
from ballast.config import ROOT
from ballast.scorecard import points

a = applicants_with_truth()
a["mark2"] = points.load_scorecard().score(a)
dev = a[a["period"] == "development"]
print(f"{'development':<16}{'applicants':>11}{'true bad':>10}"
      f"{'Mark II says':>14}")
for out in ("booked", "not_taken_up", "declined"):
    for pol in (False, True):
        g = dev[(dev["outcome"] == out) & (dev["policy"] == pol)]
        if len(g) == 0:
            continue
        name = out + (", rules" if pol else "")
        print(f"{name:<16}{len(g):>11,}{g['truth'].mean():>10.1%}"
              f"{points.bad_rate_at(g['mark2']).mean():>14.1%}")
print()
sc = dev[~dev["policy"]].copy()
edges = [540, 560, 580, 600, 620, 640]
names = ["<540", "540-559", "560-579", "580-599", "600-619",
         "620-639", "640+"]
sc["band"] = np.searchsorted(edges, sc["mark2"], side="right")
print("true bad rate by Mark II score, policy rules passed")
print(f"{'Mark II':<9}{'promise':>8}{'booked':>8}{'walked':>8}"
      f"{'declined':>10}{'n':>7}")
rows = []
for k, g in sc.groupby("band"):
    r = {"band": names[k],
         "promise": float(points.bad_rate_at(g["mark2"]).mean())}
    for out, key in (("booked", "booked"), ("not_taken_up", "walked"),
                     ("declined", "declined")):
        h = g[g["outcome"] == out]
        r[key] = float(h["truth"].mean())
        r[key + "_n"] = len(h)
    rows.append(r)
    print(f"{r['band']:<9}{r['promise']:>8.1%}{r['booked']:>8.1%}"
          f"{r['walked']:>8.1%}{r['declined']:>10.1%}"
          f"{r['declined_n']:>7,}")
print()
d = dev[(dev["decline_reason"] == "score_below_cutoff")
        & (dev["mark2"] >= 580)]
print(f"declined for score, Mark II 580+: {len(d):,}; promised "
      f"{points.bad_rate_at(d['mark2']).mean():.2%}, true "
      f"{d['truth'].mean():.2%}")
(ROOT / "code" / "09" / "07_the_truth.json").write_text(
    json.dumps(rows, indent=1) + "\n")
