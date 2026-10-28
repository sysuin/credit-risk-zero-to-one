# Lifetime PDs for the commercial book from migration matrices: the
# analysts' grades and the model's, each projected five years and set
# against what happened to clients reviewed in March 2017-2020.
import pandas as pd

import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt

con = fernhill.connect()
rv = rt.reviews(con)
rv["rd"] = pd.to_datetime(rv.review_date)
rv["dm"] = pd.to_datetime(rv.default_month)
c = rv[rv.rd.dt.year.between(2017, 2020)].copy()
c["d5"] = (c.dm > c.rd) & (c.dm <= c.rd + pd.DateOffset(years=5))
groups = {"1-3": [1, 2, 3], "4-6": [4, 5, 6], "7": [7], "8": [8],
          "9": [9], "10": [10]}
print(f"{len(c)} reviews, March 2017-2020, each followed five years;"
      f" {c.d5.sum()} were\nfollowed by a default")
analysts, models = "analysts' grades", "model's grades"
print(f"{'':<7}{analysts:>23}{models:>24}")
print(f"{'grade':<7}" + f"{'n':>5}{'seen':>8}{'matrix':>9}" * 2)
proj = {}
for col in ("grade", "model_grade"):
    m = mg.matrix(mg.panel(rv, col))
    proj[col] = mg.project(m, 5)
    c[f"p_{col}"] = c[col].astype(str).map(proj[col][5])
for name, gs in groups.items():
    row = f"{name:<7}"
    for col in ("grade", "model_grade"):
        g = c[c[col].isin(gs)]
        row += (f"{len(g):>5}{g.d5.mean():>8.1%}"
                f"{g[f'p_{col}'].mean():>9.1%}")
    print(row)
row = f"{'all':<7}"
for col in ("grade", "model_grade"):
    row += (f"{len(c):>5}{c.d5.mean():>8.1%}"
            f"{c[f'p_{col}'].mean():>9.1%}")
print(row)
a, m = proj["grade"], proj["model_grade"]
print("\nThe matrices' own one-year and five-year PDs, grades 1-4")
for g in ("1", "2", "3", "4"):
    print(f"  grade {g}: analysts {a.loc[g, 1]:.2%} / {a.loc[g, 5]:.2%}"
          f", model {m.loc[g, 1]:.2%} / {m.loc[g, 5]:.2%}")
