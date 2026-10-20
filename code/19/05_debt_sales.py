# Fernhill's two sales of old charged-off debt: what was sold, the
# price, and what the debts left unsold went on to bring in.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    WITH co AS (            -- charged-off cards and personal loans
        SELECT a.account_id, a.product, a.close_date,
               p.balance_cents AS written_off
        FROM accounts a JOIN performance p
          ON p.account_id = a.account_id AND p.month = a.close_date
        WHERE a.close_reason = 'charged_off'
          AND a.product IN ('card', 'personal')),
    sale AS (SELECT DISTINCT month FROM recoveries
             WHERE kind = 'debt_sale'),
    -- charged off at least six months before a sale, and still
    -- paying the agency something in the six months before it
    pool AS (
        SELECT co.*, s.month AS sale_month
        FROM co CROSS JOIN sale s
        WHERE co.close_date <= s.month - INTERVAL 6 MONTH),
    r AS (
        SELECT p.account_id, p.sale_month,
          sum(r.amount_cents) FILTER (WHERE r.kind =
              'collections_payment' AND r.month < p.sale_month)
              AS before,
          sum(r.amount_cents) FILTER (WHERE r.kind = 'debt_sale'
              AND r.month = p.sale_month) AS price,
          sum(r.amount_cents) FILTER (WHERE r.month > p.sale_month)
              AS after_net,
          bool_or(r.kind = 'debt_sale' AND r.month < p.sale_month)
              AS sold_earlier,
          bool_or(r.kind = 'collections_payment'
              AND r.month BETWEEN p.sale_month - INTERVAL 6 MONTH
                              AND p.sale_month - INTERVAL 1 MONTH)
              AS paying
        FROM pool p LEFT JOIN recoveries r
          ON r.account_id = p.account_id
        GROUP BY 1, 2)
    SELECT p.sale_month, r.price IS NOT NULL AS sold, count(*),
           sum(p.written_off - coalesce(r.before, 0)) AS owed,
           sum(coalesce(r.price, 0)), sum(coalesce(r.after_net, 0)),
           min(p.close_date), max(p.close_date)
    FROM pool p JOIN r USING (account_id, sale_month)
    WHERE NOT coalesce(r.sold_earlier, false) AND r.paying
    GROUP BY 1, 2 ORDER BY 1, 2 DESC""").fetchall()

print(f"{'sale':<9}{'':<6}{'debts':>6}{'still owed':>13}{'price':>11}"
      f"{'later, net':>12}{'cents':>7}")
for month, sold, n, owed, price, after, first, last in rows:
    got = price if sold else after
    print(f"{month:%b %Y} {'sold' if sold else 'kept':<6}{n:>6,}"
          f"{owed / 100:>13,.0f}{price / 100:>11,.0f}"
          f"{after / 100:>12,.0f}{100 * got / owed:>7.1f}")
print("debts charged off 6+ months before a sale, still paying the")
print("agency in the 6 months before it; dollars")
print("still owed: written off less collected before the sale;")
print("later, net: collections less costs after the sale, to Dec 2025;")
print("cents: price (sold) or later net (kept) per dollar still owed")
