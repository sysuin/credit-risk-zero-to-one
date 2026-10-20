# PL0000001's amortisation schedule, checked against Fernhill's ledger.
import json

import fernhill
from ballast.config import ROOT
from ballast.loanmath import schedule

s = schedule(1_510_000, 10.9, 60)       # cents, percent, months


def show(row):
    print(f"{row.month:>5}{row.opening / 100:>11,.2f}"
          f"{row.interest / 100:>10,.2f}{row.principal / 100:>11,.2f}"
          f"{row.closing / 100:>11,.2f}")


print(f"{'month':>5}{'opening':>11}{'interest':>10}{'principal':>11}"
      f"{'closing':>11}")
for row in s.head(3).itertuples():
    show(row)
print(f"{'...':>5}")
for row in s.tail(3).itertuples():
    show(row)

print()
print(f"total paid      ${s['payment'].sum() / 100:>10,.2f}")
print(f"of it interest  ${s['interest'].sum() / 100:>10,.2f}")

# The same questions for a 30-year mortgage Fernhill made in 2023.
con = fernhill.connect()
mortgage = con.execute("""
    SELECT amount_cents, rate_pct, term_months::INT FROM accounts
    WHERE account_id = 'MG0003444'
""").fetchone()
m = schedule(*mortgage)
print()
print(f"MG0003444: ${mortgage[0] / 100:,.0f} over {mortgage[2]} months"
      f" at {mortgage[1]}%")
print(f"{'':<26}{'PL0000001':>12}{'MG0003444':>12}")
print(f"{'interest share, month 1':<26}"
      f"{s['interest'][0] / s['payment'][0]:>12.0%}"
      f"{m['interest'][0] / m['payment'][0]:>12.0%}")
cross = [d[d["principal"] > d["interest"]]["month"].iloc[0]
         for d in (s, m)]
print(f"{'principal overtakes in':<26}{'month ' + str(cross[0]):>12}"
      f"{'month ' + str(cross[1]):>12}")
print(f"{'interest / amount lent':<26}"
      f"{s['interest'].sum() / 1_510_000:>12.0%}"
      f"{m['interest'].sum() / mortgage[0]:>12.0%}")

# Fernhill's month-end balances for every month the loan was open,
# beside the schedule's (the first row is the month it was lent).
rows = con.execute("""
    SELECT balance_cents, paid_cents FROM performance
    WHERE account_id = 'PL0000001' ORDER BY month
""").df()
ledger = rows["balance_cents"].tolist()[1:]
ours = s["closing"].tolist()[:len(ledger)]
gaps = [a - b for a, b in zip(ours, ledger)]
print()
print(f"months compared: {len(gaps)}")
print(f"largest gap, schedule minus ledger: {min(gaps)} cents")
print(f"gap in the last month: {gaps[-1]} cents")
print(f"Fernhill collected ${rows['paid_cents'].sum() / 100:,.2f};"
      f" last payment ${rows['paid_cents'].iloc[-1] / 100:,.2f}")

# Fernhill's ledger keeps fractions of a cent: it takes off the exact
# payment, $327.558..., not the $327.56 the customer is asked for.
r = 10.9 / 100 / 12
exact = 1_510_000 * r / (1 - (1 + r) ** -60)
balance = 1_510_000.0
worst = 0
for cents in ledger:
    balance = balance * (1 + r) - exact
    worst = max(worst, abs(round(balance) - cents))
print(f"largest gap, ledger's own arithmetic: {worst} cents")

# For the figure: the personal loan by month, the mortgage by year.
years = m.groupby((m["month"] - 1) // 12)[["interest", "principal"]]
json.dump({"personal": s[["interest", "principal"]].to_dict("list"),
           "mortgage": years.sum().to_dict("list")},
          open(ROOT / "code/02/03_schedule.json", "w"))
