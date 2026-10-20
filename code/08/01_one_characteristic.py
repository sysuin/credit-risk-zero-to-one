# A logistic regression on one WoE-coded characteristic, read slowly.
import numpy as np

from ballast.scorecard import model, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = s[s["fit"]]
good = model.target(train)
X = woe.encode(train, {"bureau_score": binset["bureau_score"]})

r = model.fit(X, good, ["bureau_score"])
b0, b1 = r.params["const"], r.params["bureau_score"]
odds = good.sum() / (len(good) - good.sum())
print(f"training loans {len(good):,}, goods {good.sum():,}, "
      f"odds {odds:.1f} to 1")
print(f"constant     {b0:.4f}   ln(odds) = {np.log(odds):.4f}")
print(f"coefficient  {b1:.4f}")

print()
print(f"{'bin':<10}{'WoE':>8}{'log odds':>10}{'model':>8}"
      f"{'observed':>10}")
p_bad = model.bad_rate(r, X)
bins = binset["bureau_score"].assign(train["bureau_score"])
for lab in binset["bureau_score"].labels:
    m = bins == lab
    w = binset["bureau_score"].woe[lab]
    print(f"{lab:<10}{w:>+8.3f}{b0 + b1 * w:>10.3f}"
          f"{p_bad[m].mean():>8.2%}{train.loc[m, 'bad'].mean():>10.2%}")
