# How well distance to default and the internal grade rank the next
# year's defaults among listed clients, with intervals that resample
# whole companies, because nine defaulters are very few.
import numpy as np

import fernhill
from _listed import listed_panel, next_year
from ballast.config import SEED
from ballast.scorecard import metrics as mt

con = fernhill.connect()
s = next_year(listed_panel(con))
s = s[s.internal_grade.notna()]
march = s[[m.month == 3 for m in s.month]]
samples = {
    "each March, after the review": (march, "years"),
    "every month end": (s, "months"),
}


def both(x):
    # The AUC of distance to default, and of the grade.
    return (mt.auc(x.dd, x.y), mt.auc(-x.internal_grade, x.y))


rng = np.random.default_rng(SEED)
for label, (x, unit) in samples.items():
    firms = x.company_id.unique()
    # Each company's rows, so a draw takes all of them or none.
    rows = {f: g.index.to_numpy() for f, g in x.groupby("company_id")}
    print(f"{label}\n  {len(x):,} company-{unit}; {x.y.sum()} within "
          f"a year of a default "
          f"({x[x.y == 1].company_id.nunique()} firms)")
    draws = []
    while len(draws) < 1000:
        pick = rng.choice(firms, len(firms), replace=True)
        b = x.loc[np.concatenate([rows[f] for f in pick])]
        if 0 < b.y.sum() < len(b):
            draws.append(both(b))
    draws = np.array(draws)
    est = both(x)
    for i, name in enumerate(("DD", "grade")):
        lo, hi = mt.interval(draws[:, i], 0.90)
        print(f"  AUC by {name:<7}{est[i]:>7.3f}   90% interval "
              f"{lo:.3f} to {hi:.3f}")
    diff = draws[:, 0] - draws[:, 1]
    lo, hi = mt.interval(diff, 0.90)
    print(f"  difference    {est[0] - est[1]:>+7.3f}   90% interval "
          f"{lo:+.3f} to {hi:+.3f}")
    print(f"  DD ranked better in {(diff > 0).mean():.0%} of "
          f"resamples\n")

hit = march[march.y == 1]
rank = march.groupby("month").dd.rank(pct=True)[hit.index]
grank = (-march.internal_grade).groupby(march.month) \
    .rank(pct=True)[hit.index]
print("the defaulters at their last March review, ranked among that")
print("March's listed clients (0% = riskiest)")
print(f"  by DD     median {rank.median():>4.0%}, least risky "
      f"{rank.max():>4.0%}")
print(f"  by grade  median {grank.median():>4.0%}, least risky "
      f"{grank.max():>4.0%}")
