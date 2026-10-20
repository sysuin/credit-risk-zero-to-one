# What happened to the 2020 payment-holiday borrowers in the two years
# after, against borrowers who looked like them in March 2020.
import pandas as pd

import fernhill
from ballast import collections as coll

con = fernhill.connect()
h = coll.holidays(con)
print(f"{len(h):,} holidays; {int((h['months'] == 3).sum()):,} of "
      f"three months, {int((h['months'] == 6).sum()):,} of six")
pool = con.execute("""
    WITH base AS (
        SELECT p.account_id, p.product FROM performance p
        WHERE p.month = DATE '2020-03-31' AND p.missed = 0
          AND p.scheduled_cents > 0
          AND p.product IN ('personal', 'card', 'auto', 'mortgage')),
    hol AS (SELECT account_id, count(*) AS months FROM performance
            WHERE payment_holiday GROUP BY 1),
    before AS (SELECT account_id, max(missed) AS worst FROM performance
               WHERE month BETWEEN DATE '2019-04-30'
                               AND DATE '2020-03-31'
               GROUP BY 1),
    after AS (
        SELECT account_id,
          max((missed >= 1)::INT) AS missed_any,
          max((missed >= 3)::INT) AS reached_90,
          max((status IN ('charged_off', 'vehicle_repossessed',
                          'property_sold'))::INT) AS written_off
        FROM performance
        WHERE month BETWEEN DATE '2020-10-31' AND DATE '2022-09-30'
        GROUP BY 1)
    SELECT b.account_id, b.product, coalesce(hol.months, 0) AS months,
           (before.worst > 0)::INT AS behind_before,
           coalesce(after.missed_any, 0) AS missed_any,
           coalesce(after.reached_90, 0) AS reached_90,
           coalesce(after.written_off, 0) AS written_off
    FROM base b LEFT JOIN hol USING (account_id)
    LEFT JOIN before USING (account_id)
    LEFT JOIN after USING (account_id)
    ORDER BY b.account_id""").df()
score = coll._bureau_v3(con)[["account_id", "bureau_v3"]]
pool = pool.merge(score, on="account_id", how="left")
pool["band"] = pd.qcut(pool["bureau_v3"].fillna(0), 4, labels=False)
pool["took"] = pool["months"].gt(0)
ys = ["missed_any", "reached_90", "written_off"]
print("\nConsumer accounts up to date on 31 March 2020; what they did")
print("from October 2020 to September 2022")
print(f"{'':<26}{'n':>7}{'missed':>8}{'90 days':>9}{'w/off':>8}")
for name, g in [("took a holiday", pool[pool["took"]]),
                ("  of three months", pool[pool["months"] == 3]),
                ("  of six months", pool[pool["months"] == 6]),
                ("did not", pool[~pool["took"]])]:
    print(f"{name:<26}{len(g):>7,}" + "".join(
        f"{g[y].mean():>{w}.1%}" for y, w in zip(ys, (8, 9, 8))))
cells = ["product", "band", "behind_before"]
rates = pool[~pool["took"]].groupby(cells)[ys].mean()
took = pool[pool["took"]].join(rates, on=cells, rsuffix="_like")
like = [took[f"{y}_like"].mean() for y in ys]
print(f"{'non-takers like them *':<26}{'':>7}" + "".join(
    f"{v:>{w}.1%}" for v, w in zip(like, (8, 9, 8))))
print("* same product, bureau-score quarter and arrears in the year")
print("  to March 2020, weighted to the holiday takers' mix")
