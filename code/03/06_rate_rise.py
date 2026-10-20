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
ids = [con.execute(PICK, [k]).fetchone()[0] for k in kinds]

rows = con.execute("""
    SELECT p.month, m.policy_rate_pct,
           list(p.rate_pct ORDER BY a.account_id),
           list(p.scheduled_cents ORDER BY a.account_id)
    FROM performance p
    JOIN accounts a USING (account_id)
    JOIN market_rates m USING (month)
    WHERE p.account_id IN (?, ?, ?)
      AND p.month BETWEEN '2021-12-31' AND '2024-12-31'
    GROUP BY p.month, m.policy_rate_pct
    ORDER BY p.month
""", ids).fetchall()
order = sorted(ids)                 # the lists above are in id order
col = [order.index(i) for i in ids] # fixed, variable, resetting

print("fixed", ids[0], "| variable", ids[1], "| resetting", ids[2])
print(f"{'month':<9}{'policy':>7}{'fixed':>16}{'variable':>16}"
      f"{'resetting':>16}")
for m, policy, rate, pay in rows:
    if m.month % 3 == 0:
        cells = "".join(f"{rate[c]:>7.2f}%{pay[c] / 100:>8,.0f}"
                        for c in col)
        print(f"{m:%Y-%m}  {policy:>6.2f}%{cells}")

first, last = rows[0][3], rows[-1][3]
print(f"{'change':<16}" + "".join(
    f"{last[c] / first[c] - 1:>16.0%}" for c in col))



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
    changes = match = 0
    for k in range(2, len(hist)):
        _, bal, _, old, term = hist[k - 1]
        _, _, sched, new, _ = hist[k]
        if new != old:
            left = term - (k - 1)   # payments made before this month
            changes += 1
            match += abs(payment(bal, new, left) - sched) < 1
    print(f"{kind:<10}{changes:>3} rate changes to 2025,"
          f"{match:>3} matched to the cent")

json.dump({"ids": ids, "months": [str(r[0]) for r in rows],
           "policy": [r[1] for r in rows],
           "pay": [[r[3][c] for r in rows] for c in col]},
          open(ROOT / "code/03/06_rate_rise.json", "w"))
