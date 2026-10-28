# Exercise 2.6: an emergency loan's payment-free year, and its payment.
import fernhill
from ballast.loanmath import monthly_payment, schedule

con = fernhill.connect()
amount, rate, term, booked = con.execute("""
    SELECT amount_cents, rate_pct, term_months::INT,
           payment_cents::BIGINT
    FROM accounts WHERE account_id = 'BE0000001'
""").fetchone()
print(f"booked ${booked / 100:,.2f}; the formula of 2.1 gives"
      f" ${monthly_payment(amount, rate, term) / 100:,.2f}")

rows = con.execute("""
    SELECT month, balance_cents, scheduled_cents FROM performance
    WHERE account_id = 'BE0000001' ORDER BY month LIMIT 15
""").fetchall()
# The months after opening (the first row) with nothing due.
free = []
for month, balance, scheduled in rows[1:]:
    if scheduled == 0:
        free.append(balance)
owed = free[-1]                          # the balance after the last
print(f"months with nothing due after opening: {len(free)};"
      f" owed then: ${owed / 100:,.2f}")
first_month, _, first_payment = rows[len(free) + 1]
print(f"first payment asked for: ${first_payment / 100:,.2f}"
      f" in {first_month}")
left = term - len(free)
print(f"annuity on ${owed / 100:,.2f} over {left} months:"
      f" ${monthly_payment(owed, rate, left) / 100:,.2f}")

with_year = schedule(amount, rate, term, free_months=12)
at_once = schedule(amount, rate, term)
print(f"interest over the loan, free year:"
      f" ${with_year['interest'].sum() / 100:,.2f}")
print(f"interest if repayments began at once:"
      f" ${at_once['interest'].sum() / 100:,.2f}")
