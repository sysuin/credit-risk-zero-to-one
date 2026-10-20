# How much of the LGD in use has not happened yet? For each product,
# the recovery its workouts have produced so far and the recovery the
# additive method adds for the ones still running.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
rates = lgd.discount_rates(con, w)
saved = lgd.load()["products"]
print(f"{'product':<15}{'workouts':>9}{'open':>6}{'LGD so far':>12}"
      f"{'in use':>8}{'projected':>11}")
for p in sorted(saved):
    wp = w[w["product"] == p]
    tq = lgd.recovery_triangle(wp, f, rates, cohort="quarter")
    rec = lgd.complete(tq, "additive")
    ead = tq.attrs["ead"].loc[rec.index]
    last = tq.ffill(axis=1).iloc[:, -1].loc[rec.index].fillna(0.0)
    so_far = float(1 - (last * ead).sum() / ead.sum())
    done = float((rec * ead).sum())
    proj = float(((rec - last) * ead).sum()) / done if done else 0.0
    print(f"{p:<15}{len(wp):>9,}{(wp['outcome'] == 'open').sum():>6}"
          f"{so_far:>12.1%}{saved[p]['lgd']:>8.1%}{proj:>11.1%}")
print("projected: share of the recovery in the estimate that is the")
print("method's forecast rather than cash already received")
