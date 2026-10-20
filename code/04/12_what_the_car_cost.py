# AL0001201 in dollars: promised, paid, recovered and lost.
import fernhill
from ballast.lifecycle import dollars, life

con = fernhill.connect()
lf = life(con, "A00137123")
acc = lf.accounts[0]
months = lf.months[acc["account_id"]]

lent = acc["amount_cents"]
promised = int(acc["payment_cents"]) * int(acc["term_months"])
paid = sum(m["paid_cents"] for m in months)
owed = months[-1]["balance_cents"]        # when the car was taken
at_default = lf.defaults[0]["ead_cents"]
net_recovered = sum(r["amount_cents"] for r in lf.recoveries)

print(f"{'lent':<40}{dollars(lent):>14}")
term = int(acc["term_months"])
label = f"promised: {term} payments of {dollars(acc['payment_cents'])}"
print(f"{label:<40}{dollars(promised):>14}")
print(f"{'paid by the borrower':<40}{dollars(paid):>14}")
print(f"{'owed at default (90 days)':<40}{dollars(at_default):>14}")
print(f"{'owed when the car was taken':<40}{dollars(owed):>14}")
print(f"{'recovered, net of costs':<40}{dollars(net_recovered):>14}")
loss = owed - net_recovered
print(f"{'lost against what was owed':<40}{dollars(loss):>14}"
      f"  {loss / owed:.1%}")
back = paid + net_recovered
print(f"{'cash back, against cash lent':<40}{dollars(back - lent):>14}")
print(f"{'short of what was promised':<40}"
      f"{dollars(promised - back):>14}")

# What the money cost Fernhill to fund, as in Chapter 1: each month end,
# the balance still out (owed while open, then still to recover) at
# that month's cost of funds.
rates = dict(con.execute("SELECT month, cost_of_funds_pct"
                         " FROM market_rates").fetchall())
out = {m["month"]: m["balance_cents"] for m in months}
left = owed
for r in lf.recoveries:
    left -= r["amount_cents"]
    out[r["month"]] = left
last = max(out)
funding, balance = 0.0, 0
for month in sorted(rates):
    if month < months[0]["month"] or month > last:
        continue
    balance = out.get(month, balance)
    funding += balance * rates[month] / 100 / 12
label = f"cost of funding it, {months[0]['month'].year}-{last.year}"
print(f"{label:<40}{dollars(round(funding)):>14}")
print(f"{'cash back, less funding':<40}"
      f"{dollars(round(back - lent - funding)):>14}")
