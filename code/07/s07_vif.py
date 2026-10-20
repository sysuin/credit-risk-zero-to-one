# Exercise 4: variance inflation of the shortlist, WoE-coded.
import numpy as np

from ballast.scorecard import sample, woe

s = sample.build_sample()
train = s[s["fit"]]
binset, iv = woe.fit_binset(train, train["bad"], sample.BINNING)
short = [n for n in sorted(iv, key=iv.get, reverse=True)
         if iv[n] >= 0.02]
coded = woe.encode(train, {n: binset[n] for n in short})


def vif(frame):
    """1 / (1 - R^2) of each column regressed on all the others."""
    out = {}
    for col in frame.columns:
        y = frame[col].to_numpy()
        X = frame.drop(columns=col).to_numpy()
        X = np.column_stack([np.ones(len(X)), X])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        r2 = 1 - resid.var() / y.var()
        out[col] = 1 / (1 - r2)
    return out


hit = train["bureau_score"].notna()
v_all, v_hit = vif(coded), vif(coded[hit])
print(f"{'characteristic':<24}{'VIF all':>9}{'VIF file':>10}")
for n in sorted(short, key=lambda n: -v_all[n]):
    print(f"{n:<24}{v_all[n]:>9.2f}{v_hit[n]:>10.2f}")
