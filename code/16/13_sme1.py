# SME-1, Fernhill's expert scorecard for small businesses: recomputed
# from its documentation, then judged on the loans it approved.
import numpy as np

import fernhill
from ballast.commercial import sme
from ballast.config import SEED
from ballast.scorecard import metrics as mt

con = fernhill.connect()
apps = con.execute("SELECT * FROM sme_applications ORDER BY app_id"
                   ).df()
pts = sme.sme1_points(apps)
same = (pts.total == apps.sme1_score).sum()
print(f"SME-1 recomputed from its table: {same:,} of {len(apps):,} "
      "applications match")
v3 = apps.app_date >= "2019-07-01"
half = (apps.app_date >= "2019-01-01") & (apps.app_date < "2020-01-01")
print("average owner points: 2019 H1 (bureau v2) "
      f"{pts.owner[half & ~v3].mean():.1f}, 2019 H2 (v3) "
      f"{pts.owner[half & v3].mean():.1f}")

s = sme.sample(con)
print(f"\nbooked term loans and overdrafts, 2016-2023: {len(s):,}")
print(f"bad within 24 months: {s.bad.sum()} ({s.bad.mean():.1%})")
print(f"{'score':<26}{'Gini':>7}{'interval':>16}")
rng = np.random.default_rng(SEED)
for col, label in (("sme1_score", "SME-1"),
                   ("owner_score", "owner's bureau score"),
                   ("business_score", "business score"),
                   ("years_trading", "years trading")):
    g = mt.gini(s[col], s.bad)
    lo, hi = mt.interval(mt.bootstrap(mt.gini, s[col], s.bad,
                                      n=500, rng=rng))
    print(f"{label:<26}{g:>7.3f}{lo:>9.3f} {hi:>6.3f}")
bp = sme.sme1_points(apps.set_index("app_id").loc[s.app_id])
print("\nSME-1's lines on the same loans")
for col in ("owner", "business", "years", "borrowing", "security"):
    print(f"  {col:<12}{mt.gini(bp[col].to_numpy(), s.bad):>+7.3f}")
print(f"\nowner's and business's scores, correlation "
      f"{s.owner_score.corr(s.business_score):.2f}")
print(f"{'legal form':<14}{'loans':>7}{'bad':>5}{'owner':>8}"
      f"{'business':>10}{'SME-1':>8}")
for form, g in s.groupby("legal_form"):
    print(f"{form:<14}{len(g):>7}{g.bad.sum():>5}"
          f"{mt.gini(g.owner_score, g.bad):>8.3f}"
          f"{mt.gini(g.business_score, g.bad):>10.3f}"
          f"{mt.gini(g.sme1_score, g.bad):>8.3f}")
