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
free = [r for r in rows[1:] if r[2] == 0]      # after the first row
owed = free[-1][1]
print(f"months with nothing due after opening: {len(free)};"
      f" owed then: ${owed / 100:,.2f}")
print(f"first payment asked for: ${rows[len(free) + 1][2] / 100:,.2f}"
      f" in {rows[len(free) + 1][0]}")
left = term - len(free)
print(f"annuity on ${owed / 100:,.2f} over {left} months:"
      f" ${monthly_payment(owed, rate, left) / 100:,.2f}")

with_year = schedule(amount, rate, term, free_months=12)
at_once = schedule(amount, rate, term)
print(f"interest over the loan, free year:"
      f" ${with_year['interest'].sum() / 100:,.2f}")
print(f"interest if repayments began at once:"
      f" ${at_once['interest'].sum() / 100:,.2f}")
