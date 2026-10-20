# Exercise 15.1: Meridian's need if receivable days keep rising by six
# days a year through 2027, everything else as in listing 01.
import math

import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
r = sp.ratios(s)
c = s[2025]
g = float(r.loc["revenue_growth", 2025])
grow = (1 + g) ** 2
base = st.revolver_need(s, 2025, growth=g)
for extra in (0, 6):
    days = r.loc["receivable_days", 2025] + 2 * extra
    recv = c.revenue * grow * days / 365
    wc27 = recv + (c.inventory - c.payables) * grow
    wc25 = st.working_capital(s, 2025)
    total = (c.short_term_debt + (wc27 - wc25)
             + st.SWING * wc27)
    limit = math.ceil(total / 1e8)
    print(f"receivable days {days:.0f} in 2027: need "
          f"${total / 1e8:.2f}m, limit ${limit}m")
print(f"listing 01, days unchanged: need ${base.total / 1e8:.2f}m")
