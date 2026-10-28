# Fernhill's migration matrix: where each grade's clients were at the
# next annual review, or D if they defaulted in between.
import json

import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt
from ballast.config import ROOT


def cell(share):
    """One cell: '.' for none, '<1' for under half a per cent."""
    if share == 0:
        return f"{'.':>5}"
    if share < 0.005:
        return f"{'<1':>5}"
    return f"{share * 100:>5.0f}"


con = fernhill.connect()
rv = rt.reviews(con)
p = mg.panel(rv, "grade")
counts = mg.matrix(p, shares=False)
shares = mg.matrix(p)
print(f"analysts' grades, {len(p):,} review-to-review moves, "
      "% of each row")
print(f"{'from':<5}{'n':>5}" + "".join(f"{c:>5}" for c in mg.STATES))
for g, row in shares.iterrows():
    cells = "".join(cell(v) for v in row)
    print(f"{g:<5}{counts.loc[g].sum():>5}{cells}")

print(f"\n{'in a year (not defaulted)':<27}{'analysts':>10}"
      f"{'model':>8}")
a = mg.summary(p)
m = mg.summary(mg.panel(rv, "model_grade"))
for k, label in (("stayed", "same grade"), ("one", "one notch"),
                 ("two", "two notches"),
                 ("three_plus", "three or more"),
                 ("down", "worse"), ("up", "better")):
    print(f"{label:<27}{a[k]:>10.1%}{m[k]:>8.1%}")

out = ROOT / "code" / "16" / "10_migration.json"
out.write_text(json.dumps({"states": mg.STATES,
                           "counts": counts.values.tolist()}))
