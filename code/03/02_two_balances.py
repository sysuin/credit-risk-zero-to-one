# A personal loan and a credit card from January 2019, month by month.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

# One of each, picked by rule: opened January 2019, never a payment
# missed in 36 months, amount or limit nearest the product's median.
PICK = """
    SELECT a.account_id
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = ? AND a.open_date BETWEEN '2019-01-01'
                                            AND '2019-01-31'
      AND p.month <= '2021-12-31'
    GROUP BY a.account_id, a.amount_cents
    HAVING count(*) = 36 AND max(p.missed) = 0
       AND count(*) FILTER (WHERE p.paid_cents < p.balance_cents) > 30
    ORDER BY abs(a.amount_cents - ?), a.account_id
    LIMIT 1
"""
loan = con.execute(PICK, ["personal", 1_000_000]).fetchone()[0]
card = con.execute(PICK, ["card", 550_000]).fetchone()[0]

path = {}
for acc in (loan, card):
    path[acc] = con.execute("""
        SELECT month, balance_cents, coalesce(limit_cents, 0),
               scheduled_cents, paid_cents
        FROM performance
        WHERE account_id = ? AND month <= '2021-12-31'
        ORDER BY month
    """, [acc]).fetchall()

print(f"{'':<9}{loan:>24}{card:>30}")
print(f"{'month':<9}{'owed':>10}{'paid':>14}{'owed':>10}{'paid':>10}"
      f"{'limit':>10}")
for (m, b1, _, _, p1), (_, b2, lim, _, p2) in zip(*path.values()):
    if m.month % 6 == 0 or m == path[loan][0][0]:
        print(f"{m:%Y-%m}  {b1 / 100:>10,.0f}{p1 / 100:>14,.2f}"
              f"{b2 / 100:>10,.0f}{p2 / 100:>10,.2f}"
              f"{lim / 100:>10,.0f}")

json.dump({acc: [[str(m), b, lim] for m, b, lim, _, _ in rows]
           for acc, rows in path.items()},
          open(ROOT / "code/03/02_two_balances.json", "w"))

# How all of Fernhill's open cards were used in 2025. Each month-end
# row holds the statement balance and the payment made against it.
print()
print(f"{'cards, 2025':<16}{'used of limit':>15}"
      f"{'paid in full':>14}{'minimum due':>13}")
used, full, minimum = con.execute("""
    SELECT median(balance_cents / limit_cents),    -- utilisation
           avg((paid_cents >= balance_cents)::INT),  -- paid in full
           median(scheduled_cents / balance_cents)  -- the minimum
    FROM performance
    WHERE product = 'card' AND status IN ('up_to_date', 'arrears')
      AND year(month) = 2025 AND balance_cents > 0
""").fetchone()
print(f"{'month ends':<16}{used:>15.0%}{full:>14.0%}{minimum:>13.1%}")

# And how Fernhill's instalment loans ended, once they had.
print()
print(f"{'closed loans':<16}{'repaid early':>14}{'months, early':>15}"
      f"{'term':>7}")
for product, early, months, term in con.execute("""
    SELECT product, avg((close_reason = 'prepaid')::INT),
           median(date_diff('month', open_date, close_date))
               FILTER (WHERE close_reason = 'prepaid'),
           median(term_months) FILTER (WHERE close_reason = 'prepaid')
    FROM accounts
    WHERE close_reason IN ('prepaid', 'repaid')
      AND product IN ('personal', 'auto', 'sme_term')
    GROUP BY product ORDER BY product
""").fetchall():
    print(f"{product:<16}{early:>14.0%}{months:>15.0f}{term:>7.0f}")
