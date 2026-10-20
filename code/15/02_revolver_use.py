# How Fernhill's revolvers are used: the share of the limit drawn in
# ordinary months, and in the months before a borrower defaulted.
import fernhill

con = fernhill.connect()
normal = con.execute("""
    SELECT count(*), sum(m.drawn_cents) / sum(m.limit_cents)
    FROM facility_months m JOIN facilities f USING (facility_id)
    WHERE f.kind = 'revolver' AND m.status = 'performing'
""").fetchone()
print(f"performing revolver-months: {normal[0]:,}")
print(f"  share of limits drawn: {normal[1]:.0%}")

rows = con.execute("""
    WITH d AS (
        SELECT x.facility_id, x.month AS dm, x.drawn_cents,
               x.limit_cents
        FROM facility_months x JOIN facilities f USING (facility_id)
        WHERE f.kind = 'revolver' AND x.status = 'defaulted')
    SELECT datediff('month', m.month, d.dm) AS before,
           count(*), avg(m.drawn_cents / m.limit_cents)
    FROM facility_months m JOIN d USING (facility_id)
    WHERE m.status = 'performing'
      AND datediff('month', m.month, d.dm) IN (24, 12, 6, 3, 1)
    GROUP BY 1
    UNION ALL
    SELECT 0, count(*), avg(drawn_cents / limit_cents) FROM d
    ORDER BY 1 DESC""").fetchall()
print("\nrevolvers whose borrower defaulted")
print(f"  {'months before default':<24}{'revolvers':>10}"
      f"{'drawn':>8}")
for before, n, share in rows:
    label = "at default" if before == 0 else f"{before}"
    print(f"  {label:<24}{n:>10}{share:>8.0%}")
