# A grade is a bucket: the spread of distance to default inside each
# internal grade, and the four grade-10 listed clients of October 2020.
import datetime as dt
import json
from pathlib import Path

import fernhill
from _listed import listed_panel

con = fernhill.connect()
p = listed_panel(con)
g = p[p.internal_grade.notna()]
rho = g[["dd", "internal_grade"]].corr(method="spearman").iloc[0, 1]
print(f"company-months with a grade: {len(g):,}")
print(f"  rank correlation of DD and grade: {rho:+.2f}")
print(f"\n{'grade':>5}{'months':>8}{'p10 DD':>8}{'median':>8}"
      f"{'p90 DD':>8}")
for grade, x in g.groupby("internal_grade").dd:
    q = x.quantile([0.1, 0.5, 0.9])
    print(f"{grade:>5.0f}{len(x):>8}{q[0.1]:>8.2f}{q[0.5]:>8.2f}"
          f"{q[0.9]:>8.2f}")

oct20 = g[(g.month == dt.date(2020, 10, 31))
          & (g.internal_grade == 10)]
names = dict(con.execute("SELECT company_id, name FROM companies")
             .fetchall())
print("\ngrade 10 and listed, 31 October 2020")
for r in oct20.sort_values("dd").itertuples():
    fate = (f"defaulted {r.default_month:%b %Y}"
            if isinstance(r.default_month, dt.date) else "no default")
    print(f"  {names[r.company_id]:<24} DD {r.dd:5.2f}  PD "
          f"{r.pd:6.2%}  {fate}")

alder = [c for c, n in names.items() if n == "Alder Oak Materials"]
out = p[p.company_id == alder[0]]
Path("code/17/07_grades_and_dd.json").write_text(json.dumps({
    "month": [str(m) for m in out.month], "dd": list(out.dd),
    "grade": list(out.internal_grade), "equity": list(out.equity)}))
