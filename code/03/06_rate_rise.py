# Three real mortgages' payments through the rate rise of 2022-23.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

# One of each kind, picked by rule: 25 years, opened January to June
# 2021, never a payment missed to 2024, amount nearest $250,000.
PICK = """
    SELECT a.account_id
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = 'mortgage' AND a.term_months = 300
      AND a.open_date BETWEEN '2021-01-01' AND '2021-06-30'
      AND a.rate_type = ? AND coalesce(a.fixed_months, 24) = 24
    GROUP BY a.account_id, a.amount_cents
    HAVING max(p.month) >= '2024-12-31' AND max(p.missed) = 0
    ORDER BY abs(a.amount_cents - 25000000), a.account_id
    LIMIT 1
"""
kinds = ["fixed", "variable", "fixed_then_variable"]
ids = []
for kind in kinds:
    ids.append(con.execute(PICK, [kind]).fetchone()[0])

# Each loan's rate and payment at every month end of the rise,
# beside the policy rate that month.
RISE = """
    SELECT p.month, m.policy_rate_pct, p.rate_pct, p.scheduled_cents
    FROM performance p JOIN market_rates m USING (month)
    WHERE p.account_id = ?
      AND p.month BETWEEN '2021-12-31' AND '2024-12-31'
    ORDER BY p.month
"""
loans = []
for acc in ids:
    loans.append(con.execute(RISE, [acc]).fetchall())

# One line per quarter end: the policy rate, then each loan's rate
# and payment, in the order fixed, variable, resetting.
print("fixed", ids[0], "| variable", ids[1], "| resetting", ids[2])
print(f"{'month':<9}{'policy':>7}{'fixed':>16}{'variable':>16}"
      f"{'resetting':>16}")
for fixed, variable, resetting in zip(loans[0], loans[1], loans[2]):
    month, policy = fixed[0], fixed[1]
    if month.month % 3 == 0:
        line = f"{month:%Y-%m}  {policy:>6.2f}%"
        for _, _, rate, pay in (fixed, variable, resetting):
            line += f"{rate:>7.2f}%{pay / 100:>8,.0f}"
        print(line)

# How much each payment changed from the first month to the last.
line = f"{'change':<16}"
for loan in loans:
    first_pay, last_pay = loan[0][3], loan[-1][3]
    line += f"{last_pay / first_pay - 1:>16.0%}"
print(line)


def payment(balance, rate_pct, months):
    """The level payment that repays `balance` over `months` (Chapter 2
    derives it and builds the reusable version in ballast.loanmath)."""
    r = rate_pct / 100 / 12
    return balance * r / (1 - (1 + r) ** -months)


# When the rate moves, the payment is worked out afresh: what is still
# owed, at the new rate, over the months that are left.
print()
for kind, acc in zip(["variable", "resetting"], ids[1:]):
    hist = con.execute("""
        SELECT p.month, p.balance_cents, p.scheduled_cents, p.rate_pct,
               a.term_months
        FROM performance p JOIN accounts a USING (account_id)
        WHERE account_id = ? ORDER BY p.month
    """, [acc]).fetchall()
    changes = 0
    matched = 0
    # Compare each month with the month before it.
    for k in range(2, len(hist)):
        _, owed, _, old_rate, term = hist[k - 1]
        _, _, booked, new_rate, _ = hist[k]
        if new_rate != old_rate:
            left = term - (k - 1)   # payments made before this month
            changes += 1
            if abs(payment(owed, new_rate, left) - booked) < 1:
                matched += 1
    print(f"{kind:<10}{changes:>3} rate changes to 2025,"
          f"{matched:>3} matched to the cent")

# Save the payments for the figure.
pay = []
for loan in loans:
    pay.append([row[3] for row in loan])
json.dump({"ids": ids, "months": [str(row[0]) for row in loans[0]],
           "policy": [row[1] for row in loans[0]],
           "pay": pay},
          open(ROOT / "code/03/06_rate_rise.json", "w"))
