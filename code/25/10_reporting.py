# Consumer arrears as reported at each month end, and as a report that
# flags forbearance would have shown them: holiday months and the two
# years after each holiday ends carry a flag.
import json

import fernhill
from ballast import collections as coll
from ballast.config import ROOT

con = fernhill.connect()
flags = coll.forborne(con, probation=24)
con.register("f", flags)
df = con.execute("""
    SELECT p.month, count(*) AS n,
      avg((p.missed >= 1)::INT) AS behind,
      avg(p.payment_holiday::INT) AS holiday,
      avg((f.account_id IS NOT NULL)::INT) AS forborne,
      avg((p.missed >= 1)::INT) FILTER (WHERE f.account_id IS NOT NULL
                                        AND NOT p.payment_holiday)
          AS behind_flagged,
      avg((p.missed >= 1)::INT) FILTER (WHERE f.account_id IS NULL)
          AS behind_rest
    FROM performance p
    LEFT JOIN f ON f.account_id = p.account_id AND f.month = p.month
    WHERE p.status IN ('up_to_date', 'arrears', 'default')
      AND p.product IN ('personal', 'card', 'auto', 'mortgage')
      AND p.month BETWEEN DATE '2019-07-31' AND DATE '2022-12-31'
    GROUP BY 1 ORDER BY 1""").df()
df["month"] = df["month"].astype(str)
print(f"{'month end':<11}{'30+ as':>8}{'on':>9}{'flagged':>9}"
      f"{'30+ among':>11}{'30+ among':>11}")
print(f"{'':<11}{'reported':>8}{'holiday':>9}{'forborne':>9}"
      f"{'flagged *':>11}{'the rest':>11}")
for m in ["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31",
          "2021-06-30", "2021-12-31", "2022-06-30"]:
    r = df[df["month"] == m].iloc[0]
    fl = r["behind_flagged"]
    fl = "" if fl != fl else f"{fl:.1%}"
    print(f"{m[:7]:<11}{r['behind']:>8.2%}{r['holiday']:>9.1%}"
          f"{r['forborne']:>9.1%}{fl:>11}{r['behind_rest']:>11.2%}")
print("* flagged accounts no longer on holiday")
json.dump(df.round(5).to_dict(orient="list"),
          open(ROOT / "code/25/10_reporting.json", "w"))
