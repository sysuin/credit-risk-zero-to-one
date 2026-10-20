# Exercise 29.3: double the chief credit officer's budget and see who
# approves Meridian and how many clients leave the committee's agenda.
import datetime as dt

import fernhill
from ballast import governance as gv

con = fernhill.connect()
c = gv.client_exposures(con, dt.date(2025, 3, 31))


def count():
    return {lv: sum(gv.approver(e, g) == lv
                    for e, g in zip(c.exposure_cents, c.grade))
            for lv in gv.LEVELS}


before = count()
name, budget, cap = gv.AUTHORITY[1]
gv.AUTHORITY[1] = (name, 2 * budget, cap)
after = count()
print(f"{'':<24}{'today':>8}{'doubled':>9}")
for lv in gv.LEVELS:
    print(f"{lv:<24}{before[lv]:>8}{after[lv]:>9}")
print(f"chief officer at grade 5: "
      f"${gv.authority_limit(1, 5) / 1e8:.1f}m")
print(f"Meridian's $17.0m at grade 5: "
      f"{gv.approver(1_700_000_000, 5)}")
