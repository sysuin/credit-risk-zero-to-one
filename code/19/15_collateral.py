# LGD against loan-to-value at default for cars and homes, with the
# collateral valued by the price indices in the macro table.
import json

import numpy as np
import pandas as pd

import fernhill
from ballast.config import ROOT
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
w = lgd.realised(w, f, lgd.discount_rates(con, w))
w = w[(w["outcome"] != "open") & w["lgd"].notna()]
macro = con.execute("SELECT month, house_price_index AS mortgage, "
                    "used_car_index AS auto FROM macro").df()
macro = macro.set_index(pd.to_datetime(macro["month"]))


def indexed(g, product):
    """Collateral at default: value at opening moved by the index."""
    opened = pd.to_datetime(g["open_date"]) + pd.offsets.MonthEnd(0)
    idx = macro[product]
    return g["collateral_cents"] * (g["default_month"].map(idx)
                                    / opened.map(idx)).to_numpy()


BANDS = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 9]
print(f"{'LTV at':<10}{'cars':>22}{'homes':>22}")
print(f"{'default':<10}" + f"{'n':>6}{'cured':>8}{'LGD':>8}" * 2)
out, cols = {}, {}
for p in ("auto", "mortgage"):
    g = w[w["product"] == p].copy()
    g["ltv"] = g["ead_cents"] / indexed(g, p)
    g["band"] = pd.cut(g["ltv"], BANDS, right=False)
    cols[p] = g.groupby("band", observed=False).agg(
        n=("lgd", "size"), lgd=("lgd", "mean"),
        cured=("outcome", lambda s: (s == "cured").mean()))
    out[p] = g[["ltv", "lgd"]].values.tolist()
for band in cols["auto"].index:
    cells = ""
    for p in ("auto", "mortgage"):
        r = cols[p].loc[band]
        cells += (f"{r['n']:>6.0f}{r['cured']:>8.0%}{r['lgd']:>8.1%}"
                  if r["n"] else f"{0:>6}")
    hi = "+" if band.right > 2 else f"-{band.right:.0%}"
    print(f"{f'{band.left:.0%}{hi}':<10}{cells}")

cars = np.array(out["auto"])
slope, icept = np.polyfit(cars[:, 0], cars[:, 1], 1)
print(f"\ncars: LGD = {icept:.3f} + {slope:.3f} x LTV at default")

# What a repossessed car fetched against its indexed value, by age.
sale = f[f["kind"] == "collateral_sale"].groupby("workout").agg(
    sale=("amount_cents", "sum"), month=("month", "min"))
c = w[w["product"] == "auto"].set_index("workout").join(sale,
                                                       how="inner")
c["default_month"] = pd.to_datetime(c["month"])
c["ratio"] = c["sale"] / indexed(c, "auto")
c["age"] = (c["default_month"] - pd.to_datetime(c["open_date"])
            ).dt.days / 365.25
b, a = np.polyfit(c["age"], np.log(c["ratio"]), 1)
print(f"car sale / indexed value: {np.exp(a):.0%} at age 0, "
      f"x{np.exp(b):.2f} a year")
json.dump({"auto": out["auto"], "mortgage": out["mortgage"],
           "fit": [icept, slope]},
          open(ROOT / "code/19/15_collateral.json", "w"))
