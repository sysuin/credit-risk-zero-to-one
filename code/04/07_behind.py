# Falling behind: what collections did, and how it ended.
import fernhill

con = fernhill.connect()

# Each collections action against the number of payments missed.
ladder = con.execute("""
    SELECT c.action, least(p.missed, 6) AS m, count(*)
    FROM collections c JOIN performance p USING (account_id, month)
    GROUP BY ALL ORDER BY ALL
""").fetchall()
grid = {}
for action, m, n in ladder:
    grid.setdefault(action, {})[m] = n
ORDER = ["reminder", "sms", "phone_call", "final_notice",
         "agency_referral"]
MISSED = ["1", "2", "3", "4", "5", "6+"]
print(f"{'payments missed':<17}" + "".join(f"{m:>8}" for m in MISSED))
for action in ORDER:
    print(f"{action:<17}" + "".join(f"{grid[action].get(m, 0):>8,}"
                                    for m in range(1, 7)))

# Instalment loans that ever missed a payment, by the furthest they
# fell behind, and how each account's story ended.
print()
fate = con.execute("""
    WITH worst AS (
        SELECT account_id, max(missed) AS worst FROM performance
        WHERE product IN ('personal', 'auto', 'mortgage')
        GROUP BY account_id HAVING max(missed) >= 1)
    SELECT least(worst, 6) AS w, count(*),
           count(*) FILTER (WHERE close_reason IS NULL),
           count(*) FILTER (WHERE close_reason IN
                ('repaid', 'prepaid', 'closed_by_customer')),
           count(*) FILTER (WHERE close_reason = 'charged_off'),
           count(*) FILTER (WHERE close_reason IN
                            ('vehicle_repossessed', 'property_sold'))
    FROM worst JOIN accounts USING (account_id)
    GROUP BY w ORDER BY w
""").fetchall()
print(f"{'worst missed':<13}{'loans':>7}{'open':>7}{'paid off':>10}"
      f"{'charged off':>13}{'security sold':>15}")
for w, n, still, paid, co, sold in fate:
    label = "6+" if w == 6 else str(w)
    print(f"{label:<13}{n:>7,}{still:>7,}{paid:>10,}{co:>13,}"
          f"{sold:>15,}")

cures = con.execute("""
    SELECT count(*) FROM account_events e JOIN accounts a
      USING (account_id)
    WHERE e.event = 'cure_from_default'
      AND a.product IN ('personal', 'auto', 'mortgage')
""").fetchone()[0]
print(f"cured after reaching default (events): {cures:,}")
