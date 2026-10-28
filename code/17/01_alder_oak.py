# Alder Oak Materials, a listed wholesale client, from July 2020 to
# its default: what the stock market said and what Fernhill's
# grade said, month by month.
import fernhill

con = fernhill.connect()
cid, name, dm, kind = con.execute("""
    SELECT company_id, name, default_month, kind
    FROM companies JOIN corporate_defaults USING (company_id)
    WHERE name = 'Alder Oak Materials'""").fetchone()
print(f"{name} ({cid})")
print(f"defaulted {dm:%B %Y}: {kind.replace('_', ' ')}")

rows = con.execute("""
    SELECT m.month, m.equity_value_cents,
           m.equity_value_cents / lag(m.equity_value_cents)
               OVER (ORDER BY m.month) - 1 AS change,
           (SELECT internal_grade FROM ratings r
            WHERE r.company_id = m.company_id
              AND r.internal_grade IS NOT NULL
              AND r.rating_date <= m.month
            ORDER BY r.rating_date DESC LIMIT 1) AS grade,
           (SELECT sum(drawn_cents) FROM facility_months x
            JOIN facilities f USING (facility_id)
            WHERE f.company_id = m.company_id
              AND x.month = m.month) AS drawn
    FROM market_data m
    WHERE m.company_id = ? AND m.month >= '2020-06-30'
    ORDER BY m.month""", [cid]).fetchall()
print(f"\n{'month end':<11}{'market value':>14}{'change':>9}"
      f"{'grade':>7}{'Fernhill lent':>15}")
for month, eq, ch, grade, drawn in rows[1:]:
    value = f"${eq / 1e8:.2f}m"
    lent = f"${drawn / 1e8:.2f}m"
    print(f"{month:%b %Y}{value:>17}{ch:>+9.0%}{grade:>7.0f}"
          f"{lent:>15}")

reviews = con.execute("""
    SELECT rating_date, internal_grade FROM ratings
    WHERE company_id = ? AND internal_grade IS NOT NULL
    ORDER BY rating_date""", [cid]).fetchall()
print("\nannual reviews: " + ", ".join(
    f"{d:%b %y} {g:.0f}" for d, g in reviews))
