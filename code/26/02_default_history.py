# What a satellite model has to learn from: each product's default
# rate in each year of the decade, beside that year's economy.
import fernhill
from ballast import stress

con = fernhill.connect()
h = stress.default_history(con)
t = h.pivot(index="year", columns="product", values="rate")
cols = ["personal", "card", "auto", "mortgage", "sme_term",
        "sme_overdraft", "commercial"]
short = ["pers", "card", "auto", "mortg", "term", "o/d", "comm"]
m = h.groupby("year")[["u", "policy"]].first()
print("Default rate by year (2021 definition; commercial: clients)")
print(f"{'year':<5}{'unemp':>6}{'rate':>6}"
      + "".join(f"{s:>7}" for s in short))
for y, row in t[cols].iterrows():
    print(f"{y:<5}{m.u[y]:>6.2f}{m.policy[y]:>6.2f}"
          + "".join(f"{v:>7.2%}" for v in row))
n = h.groupby("product").agg(at_risk=("at_risk", "sum"),
                             defaults=("defaults", "sum"))
print(f"{'defaults, all':<17}"
      + "".join(f"{int(n.defaults[c]):>7,}" for c in cols))
c = h[h["product"] == "commercial"].at_risk
print(f"commercial clients at risk a year: {c.min()} to {c.max()}")
