# Exercise 26.2: fit each retail satellite model without 2020 and ask
# it what 2020 would bring, given 2020's unemployment.
import fernhill
from ballast import stress

con = fernhill.connect()
h = stress.default_history(con)
u20 = h[h.year == 2020].u.iloc[0]
print(f"2020's unemployment {u20:.2f}%; fitted on 2017-19 and 2021-25")
print(f"{'':<14}{'b':>7}{'predicted':>11}{'seen':>8}{'seen/pred':>11}")
for p in ("personal", "card", "auto", "mortgage", "sme_term",
          "sme_overdraft"):
    f = stress.fit_satellite(h, p, drop_years=[2020])
    rate = stress.satellite_rate(f, {"u": u20})[0]
    seen = h[(h["product"] == p) & (h.year == 2020)].rate.iloc[0]
    print(f"{p:<14}{f['params']['u']:>7.3f}{rate:>11.2%}{seen:>8.2%}"
          f"{seen / rate:>11.2f}")
