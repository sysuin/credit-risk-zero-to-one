# LGD by product on finished workouts, and how much the choice of
# discount rate moves it.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
done = w["default_month"] <= "2021-12-31"   # four years or more ago

rates = {b: lgd.discount_rates(con, w, b)
         for b in ("none", "funding", "contract")}
r = rates["funding"][done.to_numpy()]
print(f"funding rate (cost of funds + {lgd.DISCOUNT_PREMIUM_PCT:.0f}):"
      f" {r.min():.2f}% to {r.max():.2f}%")
out = {b: lgd.pooled(lgd.realised(w[done], f, rates[b]))
       for b in rates}
print("\nworkouts that began 2016-2021, LGD weighted by EAD")
print(f"{'product':<15}{'workouts':>9}{'none':>8}{'funding':>9}"
      f"{'contract':>10}{'rate':>7}")
for p in out["funding"].index:
    rate = w.loc[done & (w["product"] == p), "rate_pct"].median()
    print(f"{p:<15}{out['funding'].loc[p, 'workouts']:>9,}"
          f"{out['none'].loc[p, 'lgd']:>8.1%}"
          f"{out['funding'].loc[p, 'lgd']:>9.1%}"
          f"{out['contract'].loc[p, 'lgd']:>10.1%}{rate:>7.2f}")
print("rate: the loans' median contract rate at default, %")
