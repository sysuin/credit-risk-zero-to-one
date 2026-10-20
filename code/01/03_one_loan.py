# One personal loan's life in dollars, from Fernhill's side of the desk.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()
ACCOUNT = "PL0000001"

loan = con.execute("""
    SELECT open_date, amount_cents, term_months::INT, rate_pct,
           payment_cents, close_date, close_reason
    FROM accounts WHERE account_id = ?
""", [ACCOUNT]).fetchone()
opened, amount, term, rate, payment, closed, reason = loan
print(f"{ACCOUNT}: ${amount / 100:,.0f} over {term} months at {rate}%,")
print(f"  ${payment / 100:,.2f} a month; opened {opened},"
      f" closed {closed} ({reason})")

# Each month Fernhill is paid something (the month a loan is paid
# off, the payoff too), and pays its own funders for the money it
# has lent out: the balance owed that month at the month's cost of
# funds.
paid, funding = con.execute("""
    SELECT sum(p.paid_cents),
           sum(p.balance_cents * r.cost_of_funds_pct / 100 / 12)
    FROM performance p JOIN market_rates r USING (month)
    WHERE p.account_id = ?
""", [ACCOUNT]).fetchone()
received = paid

interest = received - amount
print()
print(f"lent                     {amount / 100:>12,.2f}")
print(f"received back            {received / 100:>12,.2f}")
print(f"interest earned          {interest / 100:>12,.2f}")
print(f"less cost of funds       {funding / 100:>12,.2f}")
print("left to pay for staff,")
print(f"  systems and losses     {(interest - funding) / 100:>12,.2f}")

json.dump({"lent": amount, "received": received,
           "funding": funding, "opened": str(opened),
           "closed": str(closed), "reason": reason},
          open(ROOT / "code/01/03_one_loan.json", "w"))
