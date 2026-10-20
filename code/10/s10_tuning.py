# Exercise 10.1: choose the trees' size on the validation fold only.
# timeout: 300
from ballast.models import gbm
from ballast.scorecard import metrics, sample

s = sample.load_sample()
det = s[s["outcome"] != "indeterminate"]
rows = []
for leaves in (3, 7, 15):
    for least in (50, 100, 200):
        m = gbm.fit(s, params={"num_leaves": leaves,
                               "min_data_in_leaf": least})
        sc = m.score(det)
        g = [metrics.gini(sc[det["split"] == k],
                          det.loc[det["split"] == k, "bad"])
             for k in ("holdout", "out_of_time")]
        rows.append((min(m.history), leaves, least, m.rounds, *g))

best = min(rows)
by_holdout = max(rows, key=lambda r: r[4])
print(f"{'leaves':>7}{'min leaf':>9}{'trees':>7}{'val loss':>10}"
      f"{'holdout':>9}{'out of time':>13}")
for r in rows:
    print(f"{r[1]:>7}{r[2]:>9}{r[3]:>7}{r[0]:>10.5f}{r[4]:>9.3f}"
          f"{r[5]:>13.3f}")
print(f"the validation fold chooses {best[1]} leaves, {best[2]} a leaf")
print(f"the holdout would choose    {by_holdout[1]} leaves, "
      f"{by_holdout[2]} a leaf")
