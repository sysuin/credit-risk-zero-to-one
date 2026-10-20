# Cure and roll models for accounts falling one payment behind:
# fitted on 2016-2021, tested on 2022-2023, which they never saw.
import json

import pandas as pd

import fernhill
from ballast import collections as coll
from ballast.config import ROOT
from ballast.scorecard.metrics import auc

con = fernhill.connect()
e = coll.entries(con, "2016-01-01", "2023-12-31")
train, test = e[e["year"] <= 2021], e[e["year"] >= 2022].copy()
print(f"train 2016-2021: {len(train):,} entries   "
      f"test 2022-2023: {len(test):,}")

cure = coll.fit(train, "cured_3m")
roll = coll.fit(train, "rolled_90")
print(f"\n{'':<18}{'cure in 3 months':>18}{'roll to 90 days':>18}")
print(f"{'per unit of':<18}{'coef':>9}{'z':>9}{'coef':>9}{'z':>9}")
units = {"bureau_v3": "100 points", "months_on_book": "year on book",
         "log_balance": "log of balance",
         "behind_12m": "month behind *",
         "part_paid": "part paid", "no_file": "no bureau file",
         "unemployment_pct": "point unempl.", "is_card": "card",
         "is_auto": "car loan", "is_mortgage": "mortgage"}
for f in coll.FEATURES:
    a, b = cure.table().loc[f], roll.table().loc[f]
    print(f"{units[f]:<18}{a['coef']:>+9.3f}{a['z']:>9.1f}"
          f"{b['coef']:>+9.3f}{b['z']:>9.1f}")
print("* each month behind in the 12 before falling behind")


def gini(p, y):
    # metrics.auc ranks a score where high means fewer events
    return 2 * auc(-p, y) - 1


test["p_cure"] = coll.predict(cure, test)
test["p_roll"] = coll.predict(roll, test)
only = coll.fit(train, "cured_3m", ["bureau_v3", "no_file"])
p_only = coll.predict(only, test)
print("\nOn the test years (Gini; 0 is a single rate for everyone)")
g_cure = gini(test["p_cure"], test["cured_3m"])
g_roll = gini(test["p_roll"], test["rolled_90"])
print(f"  cure, full model   {g_cure:.3f}")
print(f"  cure, bureau only  {gini(p_only, test['cured_3m']):.3f}")
print(f"  roll, full model   {g_roll:.3f}")

test["fifth"] = pd.qcut(test["p_cure"], 5, labels=False)
cal = test.groupby("fifth").agg(pred=("p_cure", "mean"),
                                seen=("cured_3m", "mean"),
                                roll_pred=("p_roll", "mean"),
                                roll_seen=("rolled_90", "mean"),
                                n=("cured_3m", "size"))
print("\nBy fifth of predicted cure   cure: pred  seen"
      "   roll: pred  seen")
for k, r in cal.iterrows():
    print(f"  {k + 1} ({int(r['n']):,} entries){'':<11}"
          f"{r['pred']:>6.1%}{r['seen']:>6.1%}"
          f"{r['roll_pred']:>12.1%}{r['roll_seen']:>6.1%}")
print(f"  all{'':<23}{test['p_cure'].mean():>6.1%}"
      f"{test['cured_3m'].mean():>6.1%}"
      f"{test['p_roll'].mean():>12.1%}{test['rolled_90'].mean():>6.1%}")
json.dump({"pred": cal["pred"].round(4).tolist(),
           "seen": cal["seen"].round(4).tolist(),
           "n": cal["n"].astype(int).tolist(),
           "base": round(float(train["cured_3m"].mean()), 4),
           "deciles": test.groupby(pd.qcut(test["p_cure"], 10,
                                           labels=False))
           [["p_cure", "cured_3m"]].mean().round(4).values.tolist()},
          open(ROOT / "code/25/03_cure_model.json", "w"), indent=1)
