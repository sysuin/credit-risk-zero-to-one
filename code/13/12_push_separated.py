# Chapter 11's push groups again, with first-payment misses split into
# never paid (the fraud signature) and paid later (ordinary trouble).
import numpy as np
import pandas as pd

import fernhill
from ballast import data, fraud
from ballast.decision import policy as pol

con = fernhill.connect()
raw = data.load_applications(con, unknowns=False)
p = raw[raw["product"].astype(str).eq("personal")
        & raw["outcome"].astype(str).eq("booked")].copy()
p["dti"] = pol.dti_at_decision(p)
fp = fraud.first_payments(con)
w12 = con.execute("""
    WITH due AS (SELECT account_id, missed, row_number() OVER
                 (PARTITION BY account_id ORDER BY month) AS k
                 FROM performance WHERE product = 'personal'
                 AND scheduled_cents > 0)
    SELECT account_id, max(missed) >= 3 AS bad12 FROM due
    WHERE k <= 12 GROUP BY 1
    ORDER BY 1""").df()
p = p.merge(fp[["account_id", "first_missed", "never_paid"]],
            on="account_id").merge(w12, on="account_id")
p = p[p["never_paid"].notna()]
p["never_paid"] = p["never_paid"].astype(bool)
s = p["mark1_score"]
p["group"] = np.select([p["dti"] > 0.50, s >= 590],
                       ["looser DTI", "approved at 580 too"],
                       "added by the lower score")
day = pd.to_datetime(p["app_date"].astype("datetime64[s]"))
push = p[day.between("2021-02-01", "2022-06-30")]
rows = [(g, push[push["group"] == g]) for g in
        ("approved at 580 too", "added by the lower score",
         "looser DTI")]
rows += [("before: 575", p[day.between("2019-01-01", "2020-03-31")]),
         ("after: 580", p[day.between("2022-07-01", "2023-12-31")])]
print(f"{'personal loans':<26}{'loans':>6}{'1st':>7}{'never':>7}"
      f"{'later':>7}{'bad12*':>8}")
for name, g in rows:
    later = g["first_missed"] & ~g["never_paid"]
    rest = g[~g["never_paid"]]
    print(f"{name:<26}{len(g):>6,}{g['first_missed'].mean():>7.1%}"
          f"{g['never_paid'].mean():>7.1%}{later.mean():>7.1%}"
          f"{rest['bad12'].mean():>8.1%}")
print("1st: missed the first payment; never: missed the first three;")
print("later: missed the first, then paid; bad12*: three missed")
print("within twelve payments, among loans that paid something")
