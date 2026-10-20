# A 12-month PD for every open personal loan from what the loan shows:
# its score, its age and its arrears. Fitted on 2016-2022, it is
# tested on 2023-2024, year by year.
import fernhill
from ballast.parameters import pd as pdm
from ballast.scorecard import metrics

con = fernhill.connect()
panel = pdm.account_months(con, pdm.personal_loans(con))
known = panel[panel.complete].copy()
train = known[known.month.dt.year <= 2022]
model = pdm.fit_pd_model(train, macro=False)
print(f"{len(known):,} loan-quarters with a complete year after;\n"
      f"training 2016-2022: {len(train):,}, {train.y.sum():,} "
      "defaults")
for k, v in model.params.items():
    print(f"  {k:<12}{v:>9.3f}  (se {model.bse[k]:.3f})")

known["pd"] = model.pd(known)
test = known[known.month.dt.year >= 2023]
print(f"\nGini 2023-2024: {metrics.gini(-test.pd, test.y):.3f}")
print(f"\n{'year':<6}{'loans':>8}{'PD':>8}{'defaulted':>11}"
      f"{'gap':>8}")
for y, g in known.groupby(known.month.dt.year):
    tag = "  test" if y >= 2023 else ""
    print(f"{y:<6}{len(g):>8,}{g.pd.mean():>8.2%}{g.y.mean():>11.2%}"
          f"{g.pd.mean() - g.y.mean():>+8.2%}{tag}")
