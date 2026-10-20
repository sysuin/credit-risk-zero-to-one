# Where the money came back from on workouts that ended in a write-off,
# and how long it took.
import json

import numpy as np

import fernhill
from ballast.config import ROOT
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
lost = w[(w["outcome"] == "written_off")
         & (w["default_month"] <= "2021-12-31")]
fl = f[f["workout"].isin(lost["workout"])]
fl = fl.assign(product=fl["workout"].map(
    lost.set_index("workout")["product"]))

kinds = {"payment": "paid", "collections_payment": "agency",
         "debt_sale": "sold", "collateral_sale": "asset",
         "guarantee": "guar.", "cost": "costs"}
print("written-off workouts that began 2016-2021, % of EAD")
print(f"{'product':<13}" + "".join(f"{k:>7}" for k in kinds.values())
      + f"{'net':>6}{'90% by':>7}")
for p, g in fl.groupby("product"):
    ead = lost.loc[lost["product"] == p, "ead_cents"].sum()
    by = g.groupby("kind")["amount_cents"].sum()
    cells = "".join(f"{by.get(k, 0) / ead:>7.1%}" for k in kinds)
    m = g.groupby("months")["amount_cents"].sum().sort_index()
    share = m.cumsum() / m.sum()
    k90 = int(share[share >= 0.9].index[0])
    print(f"{p:<13}{cells}{m.sum() / ead:>6.0%}{k90:>4} mo")
print("90% by: months after default by which 90% of the net")
print("cash had arrived")

# Recovery curves for the figure: discounted, capped at EAD, on
# workouts that began 2016-2019, so each is watched for 72 months.
old = lost[lost["default_month"] <= "2019-12-31"]
rates = lgd.discount_rates(con, w)
curves = {}
for p, g in old.groupby("product"):
    tri = lgd.recovery_triangle(g, f, rates)
    ead = tri.attrs["ead"]
    curves[p] = list(np.average(tri.to_numpy(), axis=0,
                                weights=ead.to_numpy()))
json.dump(curves, open(ROOT / "code/19/04_where_it_came_from.json",
                       "w"))
