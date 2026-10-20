# One personal loan's workout, from default to the last dollar: what
# came back, when, and what it was worth on the day of default.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()
PREMIUM = 5.0           # points over the cost of funds (see the text)

# Every cash flow after a recorded default: the borrower's payments
# while in default, then everything in the recoveries table.
FLOWS = """
    WITH d AS (
        SELECT account_id, min(default_month) AS dm,
               arg_min(ead_cents, default_month) AS ead
        FROM defaults GROUP BY 1),
    flows AS (
        SELECT d.account_id, p.month, 'payment' AS kind,
               p.paid_cents AS amount
        FROM d JOIN performance p ON p.account_id = d.account_id
         AND p.month > d.dm
        UNION ALL
        SELECT account_id, month, kind, amount_cents
        FROM recoveries)
    SELECT f.*, d.dm, d.ead, m.cost_of_funds_pct + $prem AS rate,
           datediff('month', d.dm, f.month) AS months
    FROM flows f JOIN d USING (account_id)
    JOIN market_rates m ON m.month = d.dm
    WHERE f.amount <> 0"""
# The account: a personal loan charged off before 2019 that was in
# the June 2019 debt sale, with the median LGD of such loans.
pick = con.execute(f"""
    WITH f AS ({FLOWS}),
    lgd AS (
        SELECT account_id,
               1 - sum(amount / (1 + rate / 1200) ** months)
                   / any_value(ead) AS lgd
        FROM f GROUP BY 1
        HAVING bool_or(kind = 'debt_sale'))
    SELECT l.account_id FROM lgd l JOIN accounts a USING (account_id)
    WHERE a.product = 'personal' AND a.close_reason = 'charged_off'
      AND a.close_date < DATE '2019-01-01'
    ORDER BY abs(lgd - (SELECT median(lgd) FROM lgd l2
                        JOIN accounts a2 USING (account_id)
                        WHERE a2.product = 'personal'
                          AND a2.close_date < DATE '2019-01-01')),
             l.account_id
    LIMIT 1""", {"prem": PREMIUM}).fetchone()[0]

rows = con.execute(f"""
    SELECT kind, min(months), max(months), count(*), sum(amount),
           sum(amount / (1 + rate / 1200) ** months),
           any_value(ead), any_value(dm), any_value(rate)
    FROM ({FLOWS}) WHERE account_id = $acc
    GROUP BY kind ORDER BY min(months), kind""",
                   {"prem": PREMIUM, "acc": pick}).fetchall()
ead, dm, rate = rows[0][6], rows[0][7], rows[0][8]
close = con.execute("SELECT open_date, amount_cents, close_date "
                    "FROM accounts WHERE account_id = ?",
                    [pick]).fetchone()
print(f"{pick}: ${close[1] / 100:,.0f} lent {close[0]}")
print(f"defaulted {dm}, charged off {close[2]}")
print(f"owed at default (EAD)      ${ead / 100:>10,.2f}")
print(f"discount rate              {rate:>10.2f}% a year "
      f"({rate - PREMIUM:.2f} + {PREMIUM:.0f})")
print(f"\n{'':<20}{'months':>8}{'rows':>6}{'cash':>12}"
      f"{'value at default':>18}")
tot = pv = 0
for kind, m0, m1, n, cash, val, *_ in rows:
    span = f"{m0}" if m0 == m1 else f"{m0}-{m1}"
    print(f"{kind:<20}{span:>8}{n:>6}{cash / 100:>12,.2f}"
          f"{val / 100:>18,.2f}")
    tot, pv = tot + cash, pv + val
print(f"{'net':<34}{tot / 100:>12,.2f}{pv / 100:>18,.2f}")
print(f"\nloss, undiscounted   ${(ead - tot) / 100:>9,.2f}   "
      f"LGD {1 - tot / ead:.1%}")
print(f"loss, discounted     ${(ead - pv) / 100:>9,.2f}   "
      f"LGD {1 - pv / ead:.1%}")

flows = con.execute(f"""SELECT months, kind, amount FROM ({FLOWS})
    WHERE account_id = $acc ORDER BY months, kind""",
                    {"prem": PREMIUM, "acc": pick}).fetchall()
json.dump({"account": pick, "ead": ead, "default": str(dm),
           "rate": rate, "flows": flows},
          open(ROOT / "code/19/01_one_workout.json", "w"),
          default=float)
