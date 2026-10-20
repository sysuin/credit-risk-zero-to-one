# How boosted trees build one prediction, a little at a time.
import numpy as np

from ballast.models import gbm
from ballast.scorecard import sample

s = sample.load_sample()
model = gbm.fit(s)
train = s[s["fit"]]
start = np.log(train["bad"].mean() / (1 - train["bad"].mean()))
print(f"training loans {len(train):,}, bads {train['bad'].sum()}: "
      f"log odds of bad {start:.3f}")

# Chapter 8's applicant, and the first in the sample with 5+ enquiries.
oot = s[s["split"] == "out_of_time"].sort_values("app_id")
many = oot[oot["enquiries_6m"] >= 5]
two = oot.loc[[oot.index[0], many.index[0]]]
X = gbm.design(two, model.features, model.categories)
print()
print(f"{'trees':>6}" + "".join(f"{a:>22}" for a in two["app_id"]))
for k in (1, 2, 10, 50, 100, 200, model.rounds):
    lo = model.booster.predict(X, raw_score=True, num_iteration=k)
    cells = "".join(f"{v:>+11.3f}{1 / (1 + np.exp(-v)):>11.2%}"
                    for v in lo)
    print(f"{k:>6}{cells}")
print()
print("enquiries_6m        " + "".join(
    f"{int(v):>22}" for v in two["enquiries_6m"]))
print("outcome             " + "".join(
    f"{o:>22}" for o in two["outcome"]))
