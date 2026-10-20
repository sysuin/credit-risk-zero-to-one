# Does Mark II rank the loans that went bad in year two as well?
import fernhill
from ballast.scorecard import metrics, model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)

con = fernhill.connect()
late = con.execute("""
    SELECT a.account_id, max(p.missed) AS worst_13_24
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = 'personal'
      AND datediff('month', a.open_date, p.month) BETWEEN 13 AND 24
    GROUP BY a.account_id ORDER BY a.account_id""").df()
d = s[(s["split"] != "out_of_time")
      & (s["app_date"].astype(str) < "2022-01-01")].copy()
d = d.merge(late, on="account_id", how="left")
d["score"] = card.score(d)
good = d["worst_missed"] == 0
year1 = d["outcome"] == "bad"
year2 = (d["worst_missed"] < 2) & (d["worst_13_24"].fillna(0) >= 3)
print(f"development loans applied for 2016-2021: {len(d):,}")
print(f"clean in year one, no arrears: {good.sum():,}")
for name, bad in (("bad in year one", year1),
                  ("bad first in year two", year2)):
    keep = good | bad
    g = metrics.gini(d.loc[keep, "score"], bad[keep].astype(int))
    print(f"  {name:<24}{bad.sum():>5} bads, Gini vs clean {g:.3f}")
