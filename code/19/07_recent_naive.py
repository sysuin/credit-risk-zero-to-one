# The LGD of 2024's and 2025's defaults, computed as though their
# workouts were finished, against workouts that are.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
w = lgd.realised(w, f, lgd.discount_rates(con, w))
year = w["default_month"].dt.year
old = lgd.pooled(w[year <= 2021])["lgd"]


def pool(g):
    """One LGD for a set of workouts, weighted by EAD."""
    return lgd.pooled(g.assign(all=0), by="all")["lgd"].iloc[0]


print(f"{'product':<15}{'2016-21':>8}{'2024':>8}{'2025':>8}"
      f"{'open':>7}{'watched':>9}")
for p in old.index:
    cells = ""
    for y in (2024, 2025):
        g = w[(w["product"] == p) & (year == y)]
        cells += f"{pool(g):>8.1%}"
    g = w[(w["product"] == p) & (year >= 2024)]
    seen = lgd.months_observed(g).median()
    print(f"{p:<15}{old[p]:>8.1%}{cells}"
          f"{(g['outcome'] == 'open').mean():>7.0%}{seen:>6.0f} mo")
recent = w[year >= 2024]
print(f"{'all products':<15}{pool(w[year <= 2021]):>8.1%}"
      f"{pool(w[year == 2024]):>8.1%}{pool(w[year == 2025]):>8.1%}"
      f"{(recent['outcome'] == 'open').mean():>7.0%}")
print("open: share of 2024-25 workouts still in default at Dec 2025;")
print("watched: median months from default to Dec 2025")
