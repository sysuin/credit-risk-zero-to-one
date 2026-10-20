# Exercise 19.3: written-off car workouts, repossessed or not.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
w = lgd.realised(w, f, lgd.discount_rates(con, w))
cars = w[(w["product"] == "auto") & (w["outcome"] == "written_off")
         & (w["default_month"] <= "2021-12-31")].copy()
cars["how"] = cars["close_reason"].map(
    {"vehicle_repossessed": "repossessed",
     "charged_off": "charged off"})
print(f"{'':<14}{'workouts':>9}{'EAD':>14}{'LGD':>8}")
for how, g in cars.groupby("how"):
    print(f"{how:<14}{len(g):>9}{g['ead_cents'].sum() / 100:>14,.0f}"
          f"{lgd.pooled(g, by='product')['lgd'].iloc[0]:>8.1%}")
