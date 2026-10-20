# Mark II-R's promise against what each year's new loans did in their
# first twelve months, on the definition a PD uses.
import fernhill
from ballast.parameters import pd as pdm
from ballast.scorecard import points

con = fernhill.connect()
loans = pdm.personal_loans(con)
loans = loans[loans.seen12].copy()
loans["promise"] = points.bad_rate_at(loans["score"])
loans["year"] = loans.open_month.dt.year
print(f"{'opened':<8}{'loans':>7}{'score':>7}{'promised':>10}"
      f"{'defaulted':>11}{'ratio':>7}")
for y, g in loans.groupby("year"):
    print(f"{y:<8}{len(g):>7,}{g.score.mean():>7.0f}"
          f"{g.promise.mean():>10.2%}{g.d12.mean():>11.2%}"
          f"{g.promise.mean() / g.d12.mean():>7.2f}")
print(f"{'all':<8}{len(loans):>7,}{loans.score.mean():>7.0f}"
      f"{loans.promise.mean():>10.2%}{loans.d12.mean():>11.2%}"
      f"{loans.promise.mean() / loans.d12.mean():>7.2f}")
