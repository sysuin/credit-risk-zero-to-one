# Two characteristics that overlap share the credit between them.
from ballast.scorecard import model, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = s[s["fit"]]
good = model.target(train)
pair = ["bureau_score", "enquiries_6m"]
X = woe.encode(train, {n: binset[n] for n in pair})

print(f"correlation of the two WoE columns: "
      f"{X[pair[0]].corr(X[pair[1]]):+.2f}")
print()
print(f"{'model':<26}{'bureau':>8}{'enquiries':>11}{'log-lik':>11}")
fits = {}
for cols in (["bureau_score"], ["enquiries_6m"], pair):
    r = fits[" + ".join(cols)] = model.fit(X, good, cols)
    c = [f"{r.params[n]:.3f}" if n in cols else "" for n in pair]
    print(f"{' + '.join(cols):<26}{c[0]:>8}{c[1]:>11}{r.llf:>11.1f}")

both = fits[" + ".join(pair)]
for name in pair:
    lr = 2 * (both.llf - fits[name].llf)
    print(f"adding the other to {name}: likelihood ratio {lr:.1f}")
