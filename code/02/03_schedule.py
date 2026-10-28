# PL0000001's amortisation schedule, checked against Fernhill's ledger.
import json

import fernhill
from ballast.config import ROOT
from ballast.loanmath import schedule

loan = schedule(1_510_000, 10.9, 60)       # cents, percent, months


def show(row):
    print(f"{row.month:>5}{row.opening / 100:>11,.2f}"
          f"{row.interest / 100:>10,.2f}{row.principal / 100:>11,.2f}"
          f"{row.closing / 100:>11,.2f}")


def first_month_principal_wins(table):
    """The first month that repays more principal than interest."""
    later = table[table["principal"] > table["interest"]]
    return later["month"].iloc[0]


print(f"{'month':>5}{'opening':>11}{'interest':>10}{'principal':>11}"
      f"{'closing':>11}")
for row in loan.head(3).itertuples():
    show(row)
print(f"{'...':>5}")
for row in loan.tail(3).itertuples():
    show(row)

print()
print(f"total paid      ${loan['payment'].sum() / 100:>10,.2f}")
print(f"of it interest  ${loan['interest'].sum() / 100:>10,.2f}")

# The same questions for a 30-year mortgage Fernhill made in 2023.
con = fernhill.connect()
amount, rate, term = con.execute("""
    SELECT amount_cents, rate_pct, term_months::INT FROM accounts
    WHERE account_id = 'MG0003444'
""").fetchone()
mortgage = schedule(amount, rate, term)
print()
print(f"MG0003444: ${amount / 100:,.0f} over {term} months at {rate}%")
print(f"{'':<26}{'PL0000001':>12}{'MG0003444':>12}")

share_1 = loan["interest"][0] / loan["payment"][0]
share_2 = mortgage["interest"][0] / mortgage["payment"][0]
print(f"{'interest share, month 1':<26}"
      f"{share_1:>12.0%}{share_2:>12.0%}")

month_1 = "month " + str(first_month_principal_wins(loan))
month_2 = "month " + str(first_month_principal_wins(mortgage))
print(f"{'principal overtakes in':<26}"
      f"{month_1:>12}{month_2:>12}")

ratio_1 = loan["interest"].sum() / 1_510_000
ratio_2 = mortgage["interest"].sum() / amount
print(f"{'interest / amount lent':<26}"
      f"{ratio_1:>12.0%}{ratio_2:>12.0%}")

# Fernhill's month-end balances for every month the loan was open.
# The first row is the month it was lent, so it is left out.
rows = con.execute("""
    SELECT balance_cents, paid_cents FROM performance
    WHERE account_id = 'PL0000001' ORDER BY month
""").df()
ledger = rows["balance_cents"].tolist()[1:]
ours = loan["closing"].tolist()

# The gap between the schedule and the ledger, month by month.
gaps = []
for month in range(len(ledger)):
    gaps.append(ours[month] - ledger[month])
print()
print(f"months compared: {len(gaps)}")
print(f"largest gap, schedule minus ledger: {min(gaps)} cents")
print(f"gap in the last month: {gaps[-1]} cents")
collected = rows["paid_cents"].sum() / 100
last = rows["paid_cents"].iloc[-1] / 100
print(f"Fernhill collected ${collected:,.2f};"
      f" last payment ${last:,.2f}")

# Fernhill's ledger keeps fractions of a cent: it takes off the exact
# payment, $327.558..., not the $327.56 the customer is asked for.
monthly_rate = 10.9 / 100 / 12
exact = 1_510_000 * monthly_rate / (1 - (1 + monthly_rate) ** -60)
balance = 1_510_000.0
worst = 0
for cents in ledger:
    balance = balance * (1 + monthly_rate) - exact
    worst = max(worst, abs(round(balance) - cents))
print(f"largest gap, ledger's own arithmetic: {worst} cents")

# For the figure: the personal loan by month, the mortgage by year.
year = (mortgage["month"] - 1) // 12
by_year = mortgage.groupby(year)[["interest", "principal"]].sum()
figure = {"personal": loan[["interest", "principal"]].to_dict("list"),
          "mortgage": by_year.to_dict("list")}
json.dump(figure, open(ROOT / "code/02/03_schedule.json", "w"))
