# What Fernhill's commercial facilities rank as, what was owed when
# borrowers defaulted, and what security brought back afterwards.
import fernhill

con = fernhill.connect()
print("facilities by ranking and security")
for kind, senior, n, secured in con.execute("""
        SELECT kind, seniority, count(*), avg(secured::INT)
        FROM facilities GROUP BY ALL ORDER BY ALL""").fetchall():
    print(f"  {kind:<10}{senior:<8}{n:>5}   secured {secured:.0%}")

# Step 1: what each defaulted facility owed, and its limit.
# Step 2: what came back for it, split into recoveries and costs.
# Step 3: per kind of facility, the share of the limit drawn and,
#   on workouts with recoveries, what came back net of costs.
rows = con.execute("""
    WITH at_default AS (
        SELECT facility_id, drawn_cents AS owed, limit_cents
        FROM facility_months WHERE status = 'defaulted'),
    came_back AS (
        SELECT facility_id,
               sum(amount_cents) FILTER (WHERE kind <> 'cost') AS got,
               sum(amount_cents) FILTER (WHERE kind = 'cost') AS cost
        FROM corporate_recoveries GROUP BY 1)
    SELECT f.kind, f.secured, count(*) AS defaulted,
           sum(a.owed) / sum(a.limit_cents) AS drawn,
           count(b.got) AS worked_out,
           sum(b.got + b.cost) FILTER (WHERE b.got IS NOT NULL)
             / sum(a.owed) FILTER (WHERE b.got IS NOT NULL) AS net
    FROM at_default a JOIN facilities f USING (facility_id)
    LEFT JOIN came_back b USING (facility_id)
    GROUP BY ALL ORDER BY f.kind, f.secured DESC""").fetchall()
print("\nfacilities whose borrower defaulted")
print(f"  {'':<20}{'count':>6}{'drawn':>8}{'worked':>8}"
      f"{'net back':>10}")
for kind, secured, n, drawn, done, net in rows:
    label = f"{kind}, {'secured' if secured else 'unsecured'}"
    print(f"  {label:<20}{n:>6}{drawn:>8.0%}{done:>8}{net:>10.0%}")
print("  drawn: of the limit at default; net back: recoveries less")
print("  costs over what was owed, on workouts with recoveries")
