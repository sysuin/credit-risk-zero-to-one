# The debt service coverage ratio under four sets of assumptions,
# because Meridian's accounts do not say how its borrowings repay.
import fernhill
from ballast.commercial import spreading as sp

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
d = s.T
over5 = d.total_debt / sp.AMORTISATION_YEARS
due = d.short_term_debt
cases = [
    ("EBITDA basis, repaid over 5 years", "ebitda", over5),
    ("EBITDA basis, all due in a year", "ebitda", due),
    ("cash basis, repaid over 5 years", "cash", over5),
    ("cash basis, all due in a year", "cash", due),
]
print(f"{'DSCR':<36}" + "".join(f"{y:>8}" for y in s.columns))
for label, basis, principal in cases:
    v = sp.dscr(d, principal, basis)
    print(f"{label:<36}" + "".join(f"{x:>7.2f}x" for x in v))

y = 2025
print(f"\n{y}, $000")
print(f"  EBITDA - tax - capex          "
      f"{(d.ebitda - d.tax - d.capex)[y] / 1e5:>8,.0f}")
cash = d.operating_cash_flow + d.interest - d.capex
print(f"  OCF + interest - capex        {cash[y] / 1e5:>8,.0f}")
print(f"  interest                      {d.interest[y] / 1e5:>8,.0f}")
print(f"  principal, over 5 years       {over5[y] / 1e5:>8,.0f}")
print(f"  principal, all due in a year  {due[y] / 1e5:>8,.0f}")
