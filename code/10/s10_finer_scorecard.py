# Exercise 10.2: can finer bins close the gap to the challenger?
from dataclasses import replace

from ballast.models import gbm
from ballast.scorecard import metrics, model, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = s[s["fit"]]
det = model.with_file_flag(s[s["outcome"] != "indeterminate"])


def ginis(score):
    return [metrics.gini(score[det["split"] == k],
                         det.loc[det["split"] == k, "bad"])
            for k in ("holdout", "out_of_time")]


def refit(edges):
    b = dict(binset)
    for name, cut in edges.items():
        new = replace(binset[name], edges=cut, woe={})
        woe.fit(new, train[name], train["bad"])
        b[name] = new
    r, bins = model.fit_mark2(s, b)
    return model.log_odds(r, woe.encode(det, bins)), r


tries = {
    "Mark II": {},
    "enquiries 0,1,2,3,4,5+": {"enquiries_6m": [1, 2, 3, 4, 5]},
    "bureau in 20s": {"bureau_score": list(range(580, 800, 20))},
    "both": {"enquiries_6m": [1, 2, 3, 4, 5],
             "bureau_score": list(range(580, 800, 20))},
}
print(f"{'scorecard':<26}{'holdout':>9}{'out of time':>13}"
      f"{'wrong signs':>13}")
for name, edges in tries.items():
    lo, r = refit(edges)
    g = ginis(lo)
    print(f"{name:<26}{g[0]:>9.3f}{g[1]:>13.3f}"
          f"{len(model.wrong_signs(r)):>13}")
g = ginis(gbm.fit(s).score(det))
print(f"{'challenger':<26}{g[0]:>9.3f}{g[1]:>13.3f}")
