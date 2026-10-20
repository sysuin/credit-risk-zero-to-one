# Exercise 2.4: the fixed payment that clears a card in three years.
import json

from ballast.config import ROOT
from ballast.loanmath import monthly_payment, revolve

card = json.load(open(ROOT / "code/02/07_card_minimum.json"))
BALANCE, RATE = card["balance"], card["rate"]    # the median card
pay = monthly_payment(BALANCE, RATE, 36)
fixed = revolve(BALANCE, RATE, payment_cents=pay)
at_min = revolve(BALANCE, RATE)
print(f"fixed payment for 36 months: ${pay / 100:.2f}")
print(f"months revolve takes:        {len(fixed)}")
print(f"interest, fixed:   ${fixed['interest'].sum() / 100:>9,.2f}")
print(f"interest, minimum: ${at_min['interest'].sum() / 100:>9,.2f}")
saved = at_min["interest"].sum() - fixed["interest"].sum()
print(f"saved:             ${saved / 100:>9,.2f}")
