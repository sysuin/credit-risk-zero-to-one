# One personal loan falling behind, month end by month end: what was
# due, what was paid, what was owed in arrears, and the days past due.
import json

import fernhill
from ballast.config import ROOT

ACCOUNT = "PL0015999"
con = fernhill.connect()
amount, opened, rate, term, channel = con.execute("""
    SELECT amount_cents, open_date, rate_pct, term_months, channel
    FROM accounts WHERE account_id = ?""", [ACCOUNT]).fetchone()
print(f"{ACCOUNT}: ${amount / 100:,.0f}, {term:.0f} months at "
      f"{rate}%, opened {opened}, {channel}")
rows = con.execute("""
    SELECT month, scheduled_cents, paid_cents, arrears_cents, missed,
           days_past_due, status
    FROM performance
    WHERE account_id = ?
      AND month BETWEEN DATE '2024-05-31' AND DATE '2025-05-31'
    ORDER BY month""", [ACCOUNT]).fetchall()
print(f"{'month end':<12}{'due':>9}{'paid':>10}{'arrears':>10}"
      f"{'missed':>7}{'dpd':>5}  status")
for m, due, paid, arr, missed, dpd, status in rows:
    print(f"{m!s:<12}{due / 100:>9,.2f}{paid / 100:>10,.2f}"
          f"{arr / 100:>10,.2f}{missed:>7}{dpd:>5}  {status}")

json.dump([{"month": str(m), "due": d, "paid": p, "arrears": a,
            "missed": n, "dpd": dpd, "status": s}
           for m, d, p, a, n, dpd, s in rows],
          open(ROOT / "code/06/01_one_account.json", "w"))
