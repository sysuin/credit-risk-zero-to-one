# At the same Mark II score, who was booked depended on other things.
import datetime as dt

import numpy as np

from ballast.scorecard import points, reject

a = reject.applicants()
a["mark2"] = points.load_scorecard().score(a)
sc = a[(a["period"] == "development") & ~a["policy"]].copy()
edges = [540, 560, 580, 600, 620]
sc["band"] = np.searchsorted(edges, sc["mark2"], side="right")
names = ["<540", "540-559", "560-579", "580-599", "600-619", "620+"]
ws = sc["worst_status_24m"]
sc["arrears"] = np.where(ws.isna(), "no file",
                         np.where(ws > 0, "30 or 60", "none"))

print("share booked, applicants who passed the policy rules")
print(f"{'Mark II':<9}{'none':>13}{'30 or 60':>15}{'Mark I gap':>12}")
for k, g in sc.groupby("band"):
    cells = []
    for grp in ("none", "30 or 60"):
        h = g[g["arrears"] == grp]
        cells.append(f"{h['known'].mean():>6.1%} of {len(h):>5,}")
    m = g.groupby("arrears")["mark1_score"].mean()
    print(f"{names[k]:<9}{cells[0]:>13}{cells[1]:>15}"
          f"{m['none'] - m['30 or 60']:>12.0f}")
print()
ref = sc[(sc["margin"] >= -10) & (sc["margin"] < 10)]
push = ((ref["app_date"] >= dt.date(2021, 2, 1))
        & (ref["app_date"] < dt.date(2022, 7, 1)))
uw = ref[~push]
print(f"refer band outside the push: {len(uw):,} applicants")
ok = uw["outcome"].ne("declined").mean()
print(f"  underwriters approved {ok:.1%}")
