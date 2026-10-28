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
# Fit each characteristic alone, then the two together.
fits = {}
for cols in (["bureau_score"], ["enquiries_6m"], pair):
    label = " + ".join(cols)
    r = model.fit(X, good, cols)
    fits[label] = r
    coefs = []
    for name in pair:
        coefs.append(f"{r.params[name]:.3f}" if name in cols else "")
    print(f"{label:<26}{coefs[0]:>8}{coefs[1]:>11}{r.llf:>11.1f}")

# How much better the pair fits than each one alone.
both = fits[" + ".join(pair)]
for name in pair:
    lr = 2 * (both.llf - fits[name].llf)
    print(f"adding the other to {name}: likelihood ratio {lr:.1f}")
