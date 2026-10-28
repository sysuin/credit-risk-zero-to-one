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
header = f"{'year':<5}{'unemp':>6}{'rate':>6}"
for s in short:
    header += f"{s:>7}"
print(header)
# One line a year: the economy, then each product's default rate.
for y, row in t[cols].iterrows():
    line = f"{y:<5}{m.u[y]:>6.2f}{m.policy[y]:>6.2f}"
    for v in row:
        line += f"{v:>7.2%}"
    print(line)
n = h.groupby("product").agg(at_risk=("at_risk", "sum"),
                             defaults=("defaults", "sum"))
total = f"{'defaults, all':<17}"
for c in cols:
    total += f"{int(n.defaults[c]):>7,}"
print(total)
c = h[h["product"] == "commercial"].at_risk
print(f"commercial clients at risk a year: {c.min()} to {c.max()}")
