# After the account closes: what came back, what it cost, and when.
import fernhill

con = fernhill.connect()

# Unsecured loans and car loans that ended badly in 2016-2019, so
# that six years or more of their workout has been recorded.
con.execute("""
    CREATE TEMP VIEW ended AS
    SELECT a.account_id, a.product, a.close_reason, a.close_date,
           p.balance_cents AS owed
    FROM accounts a JOIN performance p
      ON p.account_id = a.account_id AND p.month = a.close_date
    WHERE a.close_reason IN ('charged_off', 'vehicle_repossessed')
      AND a.product IN ('personal', 'card', 'auto')
      AND a.close_date <= DATE '2019-12-31'
""")

# What was owed when each group of accounts closed.
owed_by_group = {}
for product, reason, owed in con.execute("""
        SELECT product, close_reason, sum(owed) FROM ended
        GROUP BY ALL""").fetchall():
    owed_by_group[(product, reason)] = owed

# What came back on each group, split by kind of recovery.
rows = con.execute("""
    SELECT e.product, e.close_reason, count(DISTINCT e.account_id),
        sum(r.amount_cents) FILTER (WHERE r.kind = 'collateral_sale'),
        sum(r.amount_cents) FILTER (WHERE r.kind IN
            ('collections_payment', 'debt_sale')),
        sum(r.amount_cents) FILTER (WHERE r.kind = 'cost')
    FROM ended e LEFT JOIN recoveries r USING (account_id)
    GROUP BY ALL ORDER BY ALL
""").fetchall()
print(f"{'closed 2016-2019':<29}{'loans':>6}{'owed $k':>9}{'sale':>6}"
      f"{'coll.':>6}{'cost':>6}{'net':>6}")
for product, reason, n, sale, coll, cost in rows:
    owed = owed_by_group[(product, reason)]
    # A group with no recoveries of a kind has None; count it as 0.
    sale = sale or 0
    coll = coll or 0
    cost = cost or 0
    net = sale + coll + cost
    label = product + ", " + reason.replace("_", " ")
    print(f"{label:<29}{n:>6,}"
          f"{owed / 1e5:>9,.0f}{sale / owed:>6.0%}{coll / owed:>6.0%}"
          f"{cost / owed:>6.0%}{net / owed:>6.0%}")

# When the money arrived, for unsecured charge-offs: the share of all
# that came back (before costs) received within each year of closing.
timing = con.execute("""
    SELECT least(datediff('month', e.close_date, r.month) // 12 + 1, 5)
             AS yr,
           sum(r.amount_cents)
    FROM ended e JOIN recoveries r USING (account_id)
    WHERE e.close_reason = 'charged_off' AND r.kind <> 'cost'
    GROUP BY yr ORDER BY yr
""").fetchall()
total = sum(v for _, v in timing)
print()
print("charged off, share of recoveries by year after closing")
running = 0
for yr, v in timing:
    running += v
    label = f"year {yr}" if yr < 5 else "later"
    print(f"  {label:<8}{v / total:>6.0%}"
          f"   by then {running / total:>5.0%}")
