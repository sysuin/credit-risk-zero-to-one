# How far the shortlisted characteristics say the same thing twice.
from itertools import combinations

from ballast.scorecard import sample, woe

s = sample.build_sample()
train = s[s["fit"]]
binset, iv = woe.fit_binset(train, train["bad"], sample.BINNING)
short = [n for n in sorted(iv, key=iv.get, reverse=True)
         if iv[n] >= 0.02]
print(f"shortlist, IV 0.02 or more: {len(short)} characteristics")

coded = woe.encode(train, {n: binset[n] for n in short})
hit = train["bureau_score"].notna()
r_all, r_hit = coded.corr(), coded[hit].corr()
pairs = list(combinations(short, 2))        # every pair, once
pairs.sort(key=lambda p: -abs(r_all.loc[p]))
print()
print(f"{'pair of WoE-coded characteristics':<44}{'all':>6}"
      f"{'file':>7}")
for a, b in pairs[:10]:
    print(f"{a[:21]:<22}{b[:21]:<22}{r_all.loc[a, b]:>+6.2f}"
          f"{r_hit.loc[a, b]:>+7.2f}")
big = sum(abs(r_all.loc[p]) >= 0.5 for p in pairs)
print(f"pairs of {len(pairs)} with |r| of 0.5 or more: {big}")
