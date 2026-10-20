# What Fernhill's commercial facilities rank as, what was owed when
# borrowers defaulted, and what security brought back afterwards.
import fernhill

con = fernhill.connect()
print("facilities by ranking and security")
for kind, senior, n, secured in con.execute("""
        SELECT kind, seniority, count(*), avg(secured::INT)
        FROM facilities GROUP BY ALL ORDER BY ALL""").fetchall():
    print(f"  {kind:<10}{senior:<8}{n:>5}   secured {secured:.0%}")

rows = con.execute("""
    WITH e AS (
        SELECT facility_id, drawn_cents AS ead, limit_cents
        FROM facility_months WHERE status = 'defaulted'),
    r AS (
        SELECT facility_id,
               sum(amount_cents) FILTER (WHERE kind <> 'cost') AS got,
               sum(amount_cents) FILTER (WHERE kind = 'cost') AS cost
        FROM corporate_recoveries GROUP BY 1)
    SELECT f.kind, f.secured, count(*) AS defaulted,
           sum(e.ead) / sum(e.limit_cents) AS drawn,
           count(r.got) AS worked_out,
           sum(r.got + r.cost) FILTER (WHERE r.got IS NOT NULL)
             / sum(e.ead) FILTER (WHERE r.got IS NOT NULL) AS net
    FROM e JOIN facilities f USING (facility_id)
    LEFT JOIN r USING (facility_id)
    GROUP BY ALL ORDER BY f.kind, f.secured DESC""").fetchall()
print("\nfacilities whose borrower defaulted")
print(f"  {'':<20}{'count':>6}{'drawn':>8}{'worked':>8}"
      f"{'net back':>10}")
for kind, sec, n, drawn, done, net in rows:
    label = f"{kind}, {'secured' if sec else 'unsecured'}"
    print(f"  {label:<20}{n:>6}{drawn:>8.0%}{done:>8}{net:>10.0%}")
print("  drawn: of the limit at default; net back: recoveries less")
print("  costs over what was owed, on workouts with recoveries")
