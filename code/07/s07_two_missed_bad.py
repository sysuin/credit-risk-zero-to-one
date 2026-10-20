# Exercise 1: count two missed payments as bad, and re-rank the IVs.
from ballast.scorecard import sample, woe

s = sample.build_sample()
train = s[s["split"] == "train"].copy()
base = train[train["outcome"] != "indeterminate"]
_, iv_base = woe.fit_binset(base, base["bad"], sample.BINNING)
train["bad2"] = (train["worst_missed"] >= 2).astype(int)
_, iv_two = woe.fit_binset(train, train["bad2"], sample.BINNING)
print(f"training loans {len(base):,} with {int(base['bad'].sum())} bads"
      f" -> {len(train):,} with {int(train['bad2'].sum())} bads")
print()
print(f"{'characteristic':<24}{'bad at 3':>9}{'bad at 2':>9}"
      f"{'change':>8}")
for name in sorted(iv_base, key=lambda n: -iv_base[n]):
    if iv_base[name] < 0.02 and iv_two[name] < 0.02:
        continue
    print(f"{name:<24}{iv_base[name]:>9.3f}{iv_two[name]:>9.3f}"
          f"{iv_two[name] - iv_base[name]:>+8.3f}")
