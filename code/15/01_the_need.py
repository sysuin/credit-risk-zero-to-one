# What Meridian asked for, and what its working capital needs: the
# borrowing it replaces, two years of growth and a swing allowance.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st
from ballast.config import ROOT

con = fernhill.connect()
amount, tenor = con.execute("""
    SELECT amount_cents, tenor_months FROM credit_requests
    WHERE request_id = 'R2025-117'""").fetchone()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
c = s[2025]
growth = float(sp.ratios(s).loc["revenue_growth", 2025])

print(f"requested: ${amount / 1e8:.1f}m revolver, {tenor} months")
print("\nend of 2025, $m")
for key, label in [("receivables", "receivables"),
                   ("inventory", "+ inventory"),
                   ("payables", "- trade payables")]:
    print(f"  {label:<28}{c[key] / 1e8:>8.2f}")
wc = st.working_capital(s, 2025)
print(f"  {'= working capital':<28}{wc / 1e8:>8.2f}")
print(f"  {'borrowings due in a year':<28}"
      f"{c.short_term_debt / 1e8:>8.2f}")
print(f"  {'borrowings due later':<28}{c.long_term_debt / 1e8:>8.2f}")

need = st.revolver_need(s, 2025, growth=growth)
print(f"\nneed, sales growing {growth:.1%} a year for two years")
labels = {"refinance": "replace short-term borrowing",
          "growth": "growth in working capital",
          "swing": f"in-year swing ({st.SWING:.0%})",
          "total": "total", "limit": "limit, next whole $1m"}
for key, label in labels.items():
    print(f"  {label:<28}{need[key] / 1e8:>8.2f}")

print("\nthe limit at other growth rates")
for g in (0.0, 0.07, growth, 0.20):
    n = st.revolver_need(s, 2025, growth=g)
    print(f"  growth {g:>6.1%}   need {n.total / 1e8:>6.2f}"
          f"   limit {n.limit / 1e8:>5.1f}")
json.dump({"need": {k: int(v) for k, v in need.items()},
           "request": int(amount)},
          open(ROOT / "code/15/01_the_need.json", "w"))
