# The challenger fitted properly: constraints, and a fold of its own.
import json

from ballast.config import ROOT
from ballast.models import gbm
from ballast.scorecard import metrics, sample

s = sample.load_sample()
train = s[s["fit"]]
val = gbm.validation_fold(train["bad"])
print(f"training loans {len(train):,} ({train['bad'].sum()} bads)")
print(f"  fitting fold    {(~val).sum():>6,} "
      f"({train.loc[~val, 'bad'].sum()} bads)")
print(f"  validation fold {val.sum():>6,} "
      f"({train.loc[val, 'bad'].sum()} bads)")
print("monotone constraints (+1: risk may only rise):")
for name, sign in gbm.MONOTONE.items():
    print(f"  {name:<24}{sign:>+3d}")

model = gbm.fit(s)
h = model.history
best = model.rounds
print()
print("validation log loss:")
print(f"  1 tree {h[0]:.5f}, {best} trees {h[best - 1]:.5f}, "
      f"{len(h)} trees {h[-1]:.5f}")
print(f"refitted on all {len(train):,} training loans with "
      f"{best} trees")
sz = gbm.size(model)
print(f"{sz['trees']} trees, {sz['leaves']:,} leaves, "
      f"{sz['splits']:,} split rules")

det = s[s["outcome"] != "indeterminate"].copy()
det["score"] = model.score(det)
print()
print(f"{'sample':<12}{'loans':>7}{'bads':>6}{'Gini':>7}")
for split in ("train", "holdout", "out_of_time"):
    d = det[det["split"] == split]
    print(f"{split:<12}{len(d):>7,}{d['bad'].sum():>6}"
          f"{metrics.gini(d['score'], d['bad']):>7.3f}")

path = ROOT / "code" / "10" / "03_fit_the_challenger.json"
path.write_text(json.dumps({"history": [round(v, 6) for v in h],
                            "best": best}) + "\n")
