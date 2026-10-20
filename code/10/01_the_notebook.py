# The comparison as the notebook made it: trees tuned on the holdout.
import lightgbm as lgb

from ballast.config import SEED
from ballast.models import gbm
from ballast.scorecard import metrics, points, sample

s = sample.load_sample()
det = s[s["outcome"] != "indeterminate"].copy()
det["mark2"] = points.load_scorecard().score(det)
train = det[det["split"] == "train"]
hold = det[det["split"] == "holdout"]

cats = gbm.categories(train)
X, Xh = (gbm.design(f, gbm.FEATURES, cats) for f in (train, hold))
params = gbm.PARAMS | {"seed": SEED}           # no constraints
booster = lgb.train(
    params, lgb.Dataset(X, train["bad"]), 3000,
    valid_sets=[lgb.Dataset(Xh, hold["bad"])],  # the holdout
    callbacks=[lgb.early_stopping(100, verbose=False)])

p = booster.predict(Xh, num_iteration=booster.best_iteration)
g_gbm = metrics.gini(-p, hold["bad"])
g_mk2 = metrics.gini(hold["mark2"], hold["bad"])
print(f"characteristics used     {len(gbm.FEATURES)}")
print(f"trees, chosen on holdout {booster.best_iteration}")
print(f"holdout loans            {len(hold):,} "
      f"({hold['bad'].sum()} bads)")
print(f"Gini, Mark II            {g_mk2:.3f}")
print(f"Gini, boosted trees      {g_gbm:.3f}")
print(f"gain                     {g_gbm - g_mk2:+.3f}")
