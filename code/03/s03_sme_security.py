# Severity of small-business term loans, secured against unsecured.
import fernhill

con = fernhill.connect()

print(f"{'sme_term':<12}{'workouts':>9}{'owed':>14}{'lost':>14}"
      f"{'severity':>10}")
for secured, n, ead, lost in con.execute("""
    WITH w AS (
        SELECT account_id, close_date,
               collateral_value_cents > 0 AS secured
        FROM accounts
        WHERE product = 'sme_term'
          AND close_reason IN ('charged_off', 'collateral_sold')
          AND close_date <= '2022-12-31'
    ),
    d AS (
        SELECT w.account_id, w.secured,
               arg_max(d.ead_cents, d.default_month) AS ead
        FROM w JOIN defaults d ON d.account_id = w.account_id
                              AND d.default_month <= w.close_date
        GROUP BY w.account_id, w.secured
    ),
    r AS (
        SELECT account_id, sum(amount_cents) AS net
        FROM recoveries GROUP BY account_id
    )
    SELECT coalesce(d.secured, false), count(*), sum(d.ead),
           sum(greatest(d.ead - coalesce(r.net, 0), 0))
    FROM d LEFT JOIN r USING (account_id)
    GROUP BY ALL ORDER BY ALL
""").fetchall():
    label = "secured" if secured else "unsecured"
    print(f"{label:<12}{n:>9}{ead / 100:>14,.0f}{lost / 100:>14,.0f}"
          f"{lost / ead:>10.0%}")
