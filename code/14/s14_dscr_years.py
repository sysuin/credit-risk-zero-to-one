# Exercise 14.3: Meridian's 2025 DSCR on both bases, with the
# borrowings repaid over three, five and seven years.
import fernhill
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
d = sp.spread(sp.accounts(con, m)).T
print(f"{'2025 DSCR':<26}{'EBITDA basis':>14}{'cash basis':>12}")
for years in (3, 5, 7):
    p = d.total_debt / years
    a = sp.dscr(d, p)[2025]
    b = sp.dscr(d, p, basis="cash")[2025]
    print(f"{f'repaid over {years} years':<26}{a:>13.2f}x{b:>11.2f}x")
p = d.short_term_debt
print(f"{'all due in a year':<26}{sp.dscr(d, p)[2025]:>13.2f}x"
      f"{sp.dscr(d, p, basis='cash')[2025]:>11.2f}x")
