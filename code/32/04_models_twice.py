# One regression fitted two ways, one boosted model run three times.
import lightgbm as lgb
import numpy as np
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score

from ballast.config import SEED
from ballast.scorecard import metrics, sample

COLS = ["bureau_score", "dti"]
s = sample.load_sample()
known = s.dropna(subset=COLS)              # statsmodels refuses NaN
train = known[known["fit"]]
oot = known[(known["split"] == "out_of_time")
            & (known["outcome"] != "indeterminate")]
print(f"training {len(train):,} loans, out of time {len(oot):,}; "
      f"{len(s) - len(known):,} no-file rows set aside")

X = sm.add_constant(train[COLS].astype(float))
y = train["bad"].astype(float)
logit = sm.Logit(y, X).fit(disp=0)
glm = sm.GLM(y, X, family=sm.families.Binomial()).fit()
print(f"{'':<14}{'Logit':>11}{'GLM':>11}{'std err':>10}")
for name in X.columns:
    print(f"{name:<14}{logit.params[name]:>11.6f}"
          f"{glm.params[name]:>11.6f}{logit.bse[name]:>10.6f}")
print(f"log-likelihood {logit.llf:.3f} and {glm.llf:.3f}")

PARAMS = {"objective": "binary", "learning_rate": 0.05,
          "num_leaves": 7, "min_data_in_leaf": 100,
          "bagging_fraction": 0.8, "bagging_freq": 1,
          "num_threads": 1, "deterministic": True,
          "force_row_wise": True, "verbose": -1}
runs = []
for seed in (SEED, SEED, SEED + 1):
    booster = lgb.train(PARAMS | {"seed": seed},
                        lgb.Dataset(train[COLS], train["bad"]), 200)
    runs.append(booster.predict(oot[COLS]))
print("same seed, same predictions:", np.array_equal(runs[0], runs[1]))
print(f"seed + 1, largest change in a PD: "
      f"{np.abs(runs[0] - runs[2]).max():.4f}")

p_logit = logit.predict(sm.add_constant(oot[COLS].astype(float)))
for name, p in (("logistic", p_logit), ("LightGBM", runs[0])):
    ours = metrics.auc(-p, oot["bad"])     # Ballast: higher is safer
    print(f"AUC {name:<9} Ballast {ours:.6f}  "
          f"scikit-learn {roc_auc_score(oot['bad'], p):.6f}")
