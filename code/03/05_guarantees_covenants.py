# What stands behind a business loan: security, guarantees, covenants.
import fernhill

con = fernhill.connect()

print("Small-business accounts, by what backs them")
print(f"{'product':<15}{'guarantee':<18}{'secured':>8}"
      f"{'unsecured':>11}")
for p, g, sec, uns in con.execute("""
    SELECT a.product, s.guarantee,
           count(*) FILTER (WHERE a.collateral_value_cents > 0),
           count(*) FILTER (WHERE a.collateral_value_cents IS NULL)
    FROM accounts a JOIN sme_applications s USING (account_id)
    GROUP BY ALL ORDER BY ALL
""").fetchall():
    print(f"{p:<15}{g:<18}{sec:>8,}{uns:>11,}")

print()
print("Small-business workouts closed with a loss, and what came back")
print(f"{'product':<15}{'security':<10}{'closed':>7}{'guarantor':>11}"
      f"{'asset sold':>12}")
for p, sec, n, guar, sold in con.execute("""
    WITH r AS (
        SELECT account_id,
               bool_or(kind = 'guarantee')       AS guar,
               bool_or(kind = 'collateral_sale') AS sold
        FROM recoveries GROUP BY account_id
    )
    SELECT a.product,
           CASE WHEN a.collateral_value_cents > 0 THEN 'secured'
                ELSE 'none' END,
           count(*), count(*) FILTER (WHERE r.guar),
           count(*) FILTER (WHERE r.sold)
    FROM accounts a LEFT JOIN r USING (account_id)
    WHERE a.product LIKE 'sme%'
      AND a.close_reason IN ('charged_off', 'collateral_sold')
    GROUP BY ALL ORDER BY ALL
""").fetchall():
    print(f"{p:<15}{sec:<10}{n:>7,}{guar:>11,}{sold:>12,}")

print()
print("Commercial facilities and their covenants (medians)")
print(f"{'kind':<10}{'secured':<9}{'count':>6}{'limit':>14}"
      f"{'max leverage':>14}{'min cover':>11}")
for kind, sec, n, lim, lev, cov in con.execute("""
    SELECT kind, secured, count(*), median(limit_cents),
           median(covenant_max_leverage),
           median(covenant_min_interest_cover)
    FROM facilities GROUP BY ALL ORDER BY ALL
""").fetchall():
    print(f"{kind:<10}{'yes' if sec else 'no':<9}{n:>6}"
          f"{f'${lim / 100:,.0f}':>14}{lev:>13.2f}x{cov:>10.2f}x")
