# Exercise 19.1: LGD on finished workouts with premiums of 0, 5 and 10
# points over the cost of funds.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
done = w[w["default_month"] <= "2021-12-31"]
out = {}
for prem in (0.0, 5.0, 10.0):
    r = lgd.discount_rates(con, w, "funding", premium_pct=prem)
    out[prem] = lgd.pooled(lgd.realised(done, f, r))["lgd"]
print(f"{'product':<15}{'+0':>8}{'+5':>8}{'+10':>8}{'move':>8}")
for p in out[0.0].index:
    print(f"{p:<15}{out[0.0][p]:>8.1%}{out[5.0][p]:>8.1%}"
          f"{out[10.0][p]:>8.1%}{out[10.0][p] - out[0.0][p]:>8.1%}")
