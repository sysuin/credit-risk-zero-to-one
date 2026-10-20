# Exercise 1: the ladder for car loans and for cards, from the
# accounts that fell behind in 2022-2023.
import fernhill
from ballast import collections as coll
from ballast import performance as perf

con = fernhill.connect()
perf.prepare(con)
e = coll.entries(con, "2022-01-01", "2023-12-31")
con.register("e", e[["root_id", "month", "product"]].assign(
    month=e["month"].dt.date))
far = con.execute("""
    SELECT e.root_id, e.month, e.product, max(h.missed) AS worst,
      max((h.status = 'vehicle_repossessed')::INT) AS taken,
      max((h.status = 'charged_off')::INT) AS charged
    FROM e JOIN history h ON h.root_id = e.root_id
     AND h.month BETWEEN e.month
         AND last_day(e.month + INTERVAL 12 MONTH)
    GROUP BY 1, 2, 3""").df()
print(f"{'':<10}{'entries':>8}{'60d':>7}{'90d':>7}{'120d':>7}"
      f"{'150d':>7}{'taken':>7}{'ch-off':>7}")
for p in ("auto", "card"):
    g = far[far["product"] == p]
    print(f"{p:<10}{len(g):>8,}" + "".join(
        f"{(g['worst'] >= k).mean():>7.1%}" for k in (2, 3, 4, 5))
        + f"{g['taken'].mean():>7.1%}{g['charged'].mean():>7.1%}")
a = far[(far["product"] == "auto") & (far["worst"] >= 4)]
print(f"car loans reaching four missed: {len(a):,}")
print(f"  car taken {a['taken'].mean():.1%}, "
      f"charged off {a['charged'].mean():.1%}")
