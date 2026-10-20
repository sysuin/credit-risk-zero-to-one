# Exercise 9.1: reweighting with its weights capped, against the truth.
from _truth import applicants_with_truth
from ballast.scorecard import metrics, reject

a = applicants_with_truth()
f = reject.frames(a)
acc, unk, hold = f["accepts"], f["unknown"], f["holdout"]
y = hold["truth"].astype(int)
base = reject.fit(acc, acc["bad"])
print(f"{'cap':<8}{'effective n':>12}{'Gini':>8}")
print(f"{'ignore':<8}{len(acc):>12,}"
      f"{metrics.gini(-base.p_bad(hold), y):>8.3f}")
for cap in (5, 10, 20, 50, None):
    t = reject.training_set("reweight", acc, unk, cap=cap)
    w = t["weight"]
    r = reject.fit(t, t["bad"], w)
    n_eff = w.sum() ** 2 / (w ** 2).sum()
    print(f"{str(cap or 'none'):<8}{n_eff:>12,.0f}"
          f"{metrics.gini(-r.p_bad(hold), y):>8.3f}")
