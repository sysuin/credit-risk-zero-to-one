# The PD reads Mark II-R's score at every age of a loan, not only in
# its first year. How well does the application score rank the next
# twelve months' defaults as loans grow older?
import pandas as pd

import fernhill
from _cache import loans
from ballast.parameters import pd as pdm
from ballast.scorecard import metrics

con = fernhill.connect()
panel = pdm.account_months(con, loans(con))
known = panel[panel["complete"]].copy()
model = pdm.fit_pd_model(known[known["month"].dt.year <= 2022])
known["pd"] = model.pd(known)
known["age"] = pdm.mob_group(known["mob"])
book = panel[panel["month"] == pd.Timestamp("2025-12-31")]
share = pd.Series(pdm.mob_group(book["mob"])).value_counts(
    normalize=True)

print("Loan-quarters 2016-2024 with a complete year after, by months")
print("on book: Gini of the application score alone and of the")
print("12-month PD (score, age, arrears, economy; fitted 2016-2022)")
print(f"{'on book':<9}{'rows':>9}{'defaults':>10}{'score':>8}"
      f"{'PD':>8}{'Dec 2025 book':>15}")
for g, x in known.groupby("age", observed=True):
    print(f"{g:<9}{len(x):>9,}{x['y'].sum():>10,}"
          f"{metrics.gini(x['score'], x['y']):>8.3f}"
          f"{metrics.gini(-x['pd'], x['y']):>8.3f}{share[g]:>15.1%}")
up = known[known["missed"] == 0]
young, old = up[up["mob"] <= 12], up[up["mob"] > 24]
print(f"\nUp to date at the quarter end: score Gini "
      f"{metrics.gini(young['score'], young['y']):.3f} in the first"
      f"\nyear, {metrics.gini(old['score'], old['y']):.3f} after two")
