# Do losses given default rise in bad years? By year of default for
# the main products, and for cars by the used-car market at the sale.
import pandas as pd

import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
w = lgd.realised(w, f, lgd.discount_rates(con, w))
macro = con.execute("SELECT month, unemployment_pct AS u, "
                    "used_car_index AS car FROM macro").df()
macro = macro.set_index(pd.to_datetime(macro["month"]))
w["year"] = w["default_month"].dt.year
done = w[w["year"].between(2017, 2021)]

PRODUCTS = ["card", "personal", "sme_overdraft", "auto", "sme_term"]
print("LGD by year of default (workouts in brackets)")
NAMES = ["card", "personal", "overdraft", "auto", "sme_term"]
print(f"{'year':<5}{'jobless':>8}" + "".join(f"{n:>11}"
                                           for n in NAMES))
tab = lgd.pooled(done, by=["year", "product"])
for y in range(2017, 2022):
    u = macro.loc[macro.index.year == y, "u"].mean()
    cells = "".join(f"{tab.loc[(y, p), 'lgd']:>6.0%}"
                    f"({tab.loc[(y, p), 'workouts']:>3})"
                    for p in PRODUCTS)
    print(f"{y:<5}{u:>7.1f}%{cells}")

sales = f[f["kind"] == "collateral_sale"].groupby("workout")["month"]
cars = w[w["product"] == "auto"].set_index("workout")
cars = cars.loc[cars.index.intersection(sales.min().index)]
sold = pd.to_datetime(sales.min().loc[cars.index])
opened = pd.to_datetime(cars["open_date"]) + pd.offsets.MonthEnd(0)
cars["index_ratio"] = (sold.map(macro["car"]).to_numpy()
                       / opened.map(macro["car"]).to_numpy())
cars["sale_year"] = sold.dt.year
print("\nrepossessed cars by year of sale")
print(f"{'sold':<6}{'cars':>6}{'used-car index':>16}{'LGD':>7}")
for y, g in cars.groupby("sale_year"):
    print(f"{y:<6}{len(g):>6}{g['index_ratio'].median():>15.2f}x"
          f"{g['lgd'].mean():>7.1%}")
print("used-car index: at the sale over at the loan's opening (median)")
up = cars["index_ratio"] >= 1
print(f"index at or above opening: LGD {cars.loc[up, 'lgd'].mean():.1%}"
      f" ({up.sum()}); below: {cars.loc[~up, 'lgd'].mean():.1%}"
      f" ({(~up).sum()})")
