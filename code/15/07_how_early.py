# How early, and how often wrongly, covenants at different levels
# trip: every company-year in Fernhill's book, whatever was signed.
import json

import pandas as pd

import fernhill
from _book import accounts, arrives
from ballast.commercial import structure as st
from ballast.config import ROOT

con = fernhill.connect()
acc = accounts(con)
r = st.breaches(acc.debt, acc.ebitda, acc.interest, 1.0, 1.0)
acc["leverage"], acc["cover"] = r.leverage, r.cover
acc["lead"] = [(dm - arrives(fy)).days / 30.44 if pd.notna(dm) else None
               for dm, fy in zip(acc.dm, acc.fy)]
groups = [acc[acc.k == k] for k in (1, 2, 3)] + [acc[acc.k.isna()]]

print(f"defaulters {len(groups[0])}; other company-years "
      f"{len(groups[3])}")
for label, g in (("last accounts", groups[0]),
                 ("a year earlier", groups[1])):
    print(f"  {label} arrive {g.lead.median():.0f} months before "
          f"default (range {g.lead.min():.0f} to {g.lead.max():.0f})")

print(f"\n{'share above the cap':<24}{'last':>7}{'-1 yr':>7}"
      f"{'-2 yrs':>7}{'others':>8}")
for cap in (3.25, 4.0, 5.0, 6.0, 8.0):
    v = [(g.leverage > cap).mean() for g in groups]
    print(f"  debt / EBITDA > {cap:<6.2f}" + "".join(
        f"{x:>7.0%}" for x in v[:3]) + f"{v[3]:>8.0%}")
for floor in (4.0, 3.0, 2.0):
    v = [(g.cover < floor).mean() for g in groups]
    print(f"  EBITDA / int. < {floor:<6.2f}" + "".join(
        f"{x:>7.0%}" for x in v[:3]) + f"{v[3]:>8.0%}")

print("\nmedian debt / EBITDA, by accounts before default")
path = acc[acc.k <= 6].groupby("k").leverage.quantile(
    [0.25, 0.5, 0.75]).unstack()
for k, row in path.iterrows():
    print(f"  {int(k)} before: {row[0.5]:>5.1f}x  "
          f"(middle half {row[0.25]:.1f}x to {row[0.75]:.1f}x)")
q = groups[3].leverage.quantile([0.25, 0.5, 0.75])
print(f"  never defaulted: {q[0.5]:.1f}x  "
      f"(middle half {q[0.25]:.1f}x to {q[0.75]:.1f}x)")
json.dump({"k": [int(k) for k in path.index],
           "q": {str(c): [float(v) for v in path[c]]
                 for c in path.columns},
           "never": [float(v) for v in q]},
          open(ROOT / "code/15/07_how_early.json", "w"))
