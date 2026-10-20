# Three segments of the accounts that fell behind in 2022-2023, by the
# cure model's prediction: how they behaved, and where the losses were.
import pandas as pd

import fernhill
from ballast import collections as coll

con = fernhill.connect()
e = coll.entries(con, "2016-01-01", "2023-12-31")
model = coll.fit(e[e["year"] <= 2021], "cured_3m")
test = e[e["year"] >= 2022].copy()
test["p_cure"] = coll.predict(model, test)
later = coll.later_outcomes(con, test, horizon=12)
test = test.merge(later, on=["root_id", "month"], how="left")
test["loss"] = (test["off_cents"] - test["rec_cents"]).fillna(0)

edges = [0, 0.60, 0.75, 1]
names = ["likely to roll", "in between", "likely to cure"]
test["segment"] = pd.cut(test["p_cure"], edges, labels=names)
total_loss = test["loss"].sum()
print(f"{'segment':<16}{'share':>7}{'pred':>7}{'cured':>7}"
      f"{'rolled':>8}{'w/off':>7}{'loss':>7}")
for k, g in test.groupby("segment", observed=True):
    print(f"{k:<16}{len(g) / len(test):>7.0%}{g['p_cure'].mean():>7.0%}"
          f"{g['cured_3m'].mean():>7.0%}{g['rolled_90'].mean():>8.0%}"
          f"{g['written_off'].mean():>7.0%}"
          f"{g['loss'].sum() / total_loss:>7.0%}")
print("pred, cured: predicted and seen cure within three months;")
print("w/off: written off within 12 months; loss: share of the")
print(f"${total_loss / 100:,.0f} written off less recovered to date")
