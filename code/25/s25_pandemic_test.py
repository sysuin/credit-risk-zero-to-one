# Exercise 2: the cure model fitted on 2016-2019 and tested on
# 2020-2021, the years of the pandemic and the payment holidays.

import fernhill
from ballast import collections as coll
from ballast.scorecard.metrics import auc

con = fernhill.connect()
e = coll.entries(con, "2016-01-01", "2023-12-31")
splits = ((2019, (2020, 2021)), (2021, (2022, 2023)))
for train_to, test_years in splits:
    tr = e[e["year"] <= train_to]
    te = e[e["year"].between(*test_years)].copy()
    m = coll.fit(tr, "cured_3m")
    te["p"] = coll.predict(m, te)
    gini = 2 * auc(-te["p"], te["cured_3m"]) - 1
    print(f"fit to {train_to}, test {test_years[0]}-{test_years[1]}: "
          f"Gini {gini:.3f}, predicted {te['p'].mean():.1%}, "
          f"seen {te['cured_3m'].mean():.1%}")
    t = m.table()
    u = t.loc["unemployment_pct", "coef"]
    print(f"  unemployment coef {u:+.3f}"
          f"  bureau coef {t.loc['bureau_v3', 'coef']:+.3f}")
    if train_to == 2019:
        q = te["month"].dt.to_period("Q")
        by = te.groupby(q)[["p", "cured_3m"]]
        print("  by quarter:  predicted  seen")
        for q, r in by.mean().iterrows():
            print(f"  {str(q):<12}{r['p']:>9.1%}{r['cured_3m']:>7.1%}")
