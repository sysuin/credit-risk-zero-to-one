# Recovery by months since default, one row per year of default: the
# triangle, and two ways of finishing its unfinished rows.
import fernhill
from ballast.parameters import lgd

con = fernhill.connect()
w = lgd.workouts(con)
f = lgd.cash_flows(con, w)
rates = lgd.discount_rates(con, w)
w = lgd.realised(w, f, rates)

cards = w[w["product"] == "card"]
tri = lgd.recovery_triangle(cards, f, rates)
cols = [3, 6, 12, 24, 36, 48, 60]
print("cards: recovered, % of EAD, by months since default")
print(f"{'default':<9}" + "".join(f"{c:>7}" for c in cols))
for c, row in tri.iterrows():
    cells = "".join("      ." if row[k] != row[k] else
                    f"{row[k]:>7.1%}" for k in cols)
    print(f"{c:<9}{cells}")

print(f"\n{'':<9}{'cards':^24}{'personal loans':^24}")
print(f"{'default':<9}" + f"{'naive':>8}{'chain':>8}{'added':>8}" * 2)
out = {}
for p in ("card", "personal"):
    g = w[w["product"] == p]
    tq = lgd.recovery_triangle(g, f, rates, cohort="quarter")
    out[p] = (lgd.pooled(g, by=g["default_month"].dt.year)["lgd"],
              lgd.completed_lgd(tq, "chain"),
              lgd.completed_lgd(tq, "additive"))
for y in range(2019, 2026):
    cells = ""
    for p in ("card", "personal"):
        naive, chain, add = out[p]
        cells += (f"{naive[y]:>8.1%}{chain[str(y)]:>8.1%}"
                  f"{add[str(y)]:>8.1%}")
    print(f"{y:<9}{cells}")
