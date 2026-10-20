# The uplift: an assumption about rejects the data cannot check.
# timeout: 300
import numpy as np

from _truth import applicants_with_truth
from ballast.config import SEED
from ballast.scorecard import reject

a = applicants_with_truth()
f = reject.frames(a)
acc, unk, hold = f["accepts"], f["unknown"], f["holdout"]
retro = reject.retro()
methods = ("hard cut-off", "parcelling", "fuzzy")
print(f"{'method':<14}{'uplift':>7}{'Gini':>7}{'declines':>10}"
      f"{'true':>7}{'booked':>8}{'true':>7}")
for up in (1.0, 1.5, 2.0):
    fits = reject.fit_all(acc, unk, retro, np.random.default_rng(SEED),
                          uplift=up, methods=methods)
    for m in methods:
        c = reject.compare(fits[m].p_bad(hold), hold["truth"],
                           hold["outcome"])
        print(f"{m:<14}{up:>7.1f}{c['gini']:>7.3f}"
              f"{c['declined_predicted']:>10.1%}"
              f"{c['declined_actual']:>7.1%}"
              f"{c['booked_predicted']:>8.1%}"
              f"{c['booked_actual']:>7.1%}")
print()
base = reject.fit(acc, acc["bad"])
d = hold[hold["outcome"] == "declined"].copy()
d["p"] = base.p_bad(d).to_numpy()
d["band"] = np.searchsorted([540, 560, 580, 600], base.score(d),
                            side="right")
names = ["<540", "540-559", "560-579", "580-599", "600+"]
print("the uplift each band of declines needed, booked-only model")
print(f"{'score':<9}{'declined':>9}{'predicted':>11}{'true':>7}"
      f"{'needed':>8}")
for k, g in d.groupby("band"):
    print(f"{names[k]:<9}{len(g):>9,}{g['p'].mean():>11.1%}"
          f"{g['truth'].mean():>7.1%}"
          f"{g['truth'].mean() / g['p'].mean():>8.2f}")
