# Exercise 2.2: when MG0003444's balance falls below half the loan.
from ballast.loanmath import schedule

AMOUNT = 39_600_000                      # $396,000, in cents
loan = schedule(AMOUNT, 6.75, 360)

# Keep the months with the balance below half; take the first.
below_half = loan[loan["closing"] < AMOUNT / 2]
month = int(below_half["month"].iloc[0])

# Every month up to and including that one.
paid = loan[loan["month"] <= month]
print(f"balance first below half in month {month}"
      f" ({month / 12:.1f} years)")
print(f"payments made by then: ${paid['payment'].sum() / 100:,.0f}")
print(f"  of which interest:   ${paid['interest'].sum() / 100:,.0f}"
      f" ({paid['interest'].sum() / paid['payment'].sum():.0%})")
