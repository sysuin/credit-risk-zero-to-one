# Exercise 16.3: five-year default rates projected from the analysts'
# matrix and from the model's.
import fernhill
from ballast.commercial import migration as mg
from ballast.commercial import rating as rt

con = fernhill.connect()
rv = rt.reviews(con)
print(f"{'grade':<7}{'years':>6}{'analysts':>10}{'model':>8}")
a = mg.project(mg.matrix(mg.panel(rv, "grade")), 5)
m = mg.project(mg.matrix(mg.panel(rv, "model_grade")), 5)
for g in ("4", "8"):
    for y in (1, 3, 5):
        print(f"{g:<7}{y:>6}{a.loc[g, y]:>10.1%}{m.loc[g, y]:>8.1%}")
