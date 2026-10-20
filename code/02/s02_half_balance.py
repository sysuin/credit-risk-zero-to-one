# Exercise 2.2: when MG0003444's balance falls below half the loan.
from ballast.loanmath import schedule

AMOUNT = 39_600_000
s = schedule(AMOUNT, 6.75, 360)
half = s[s["closing"] < AMOUNT / 2].iloc[0]
month = int(half["month"])
paid = s[s["month"] <= month]
print(f"balance first below half in month {month}"
      f" ({month / 12:.1f} years)")
print(f"payments made by then: ${paid['payment'].sum() / 100:,.0f}")
print(f"  of which interest:   ${paid['interest'].sum() / 100:,.0f}"
      f" ({paid['interest'].sum() / paid['payment'].sum():.0%})")
