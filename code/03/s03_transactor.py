# The January 2019 card whose holder cleared the bill most often.
import fernhill

con = fernhill.connect()

# Opened January 2019, open three years with nothing missed; ranked by
# the months in which the payment cleared the statement balance.
card, cleared = con.execute("""
    WITH p AS (
        SELECT a.account_id, p.month, p.paid_cents, p.missed,
               p.balance_cents
        FROM accounts a JOIN performance p USING (account_id)
        WHERE a.product = 'card'
          AND a.open_date BETWEEN '2019-01-01' AND '2019-01-31'
          AND p.month <= '2021-12-31'
    )
    SELECT account_id,
           count(*) FILTER (WHERE paid_cents >= balance_cents
                              AND balance_cents > 0)
    FROM p
    GROUP BY account_id
    HAVING count(*) = 36 AND max(missed) = 0
    ORDER BY 2 DESC, account_id
    LIMIT 1
""").fetchone()
print(f"{card}: cleared the bill in {cleared} of 36 months")

rows = con.execute("""
    SELECT month, balance_cents, paid_cents, limit_cents
    FROM performance
    WHERE account_id = ? AND month <= '2021-12-31'
    ORDER BY month
""", [card]).fetchall()
print(f"{'month':<9}{'owed':>10}{'paid':>10}{'limit':>10}")
for m, owed, paid, limit in rows:
    if m.month % 6 == 0 or m == rows[0][0]:
        print(f"{m:%Y-%m}  {owed / 100:>10,.0f}{paid / 100:>10,.2f}"
              f"{limit / 100:>10,.0f}")
