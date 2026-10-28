# What tomorrow's model can learn from: only the loans Fernhill made.
import fernhill

con = fernhill.connect()

# Step 1: every personal, card and car application, and where it
# scored against the cut-off.
con.execute("""
    CREATE TEMP VIEW apps AS
    SELECT app_id, account_id, outcome,
           CASE WHEN mark1_score < cutoff - 10 THEN '1 below refer'
                WHEN mark1_score < cutoff + 10 THEN '2 refer band'
                ELSE '3 above refer' END AS band
    FROM applications WHERE product IN ('personal', 'card', 'auto')
""")

# Step 2: for loans with a full year on the book, whether each was
# ever 90 days behind in that year (the label a scorecard learns from).
con.execute("""
    CREATE TEMP VIEW first_year AS
    SELECT a.account_id, max(p.missed) >= 3 AS bad
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.open_date <= DATE '2024-12-31'
      AND p.month < a.open_date + INTERVAL 12 MONTH
      AND a.predecessor_id IS NULL
    GROUP BY a.account_id
""")

# Step 3: by band, how many applied, became loans and carry a label.
rows = con.execute("""
    SELECT band, count(*),
           count(*) FILTER (WHERE outcome = 'booked'),
           count(f.bad), count(*) FILTER (WHERE f.bad)
    FROM apps LEFT JOIN first_year f USING (account_id)
    GROUP BY band ORDER BY band
""").fetchall()
print(f"{'score against cut-off':<22}{'applied':>9}{'booked':>8}"
      f"{'labelled':>10}{'bad':>6}{'bad rate':>10}")
for band, applied, booked, labelled, bad in rows:
    rate = f"{bad / labelled:.1%}" if labelled else "-"
    print(f"{band[2:]:<22}{applied:>9,}{booked:>8,}{labelled:>10,}"
          f"{bad:>6,}{rate:>10}")
applied = sum(r[1] for r in rows)
labelled = sum(r[3] for r in rows)
print(f"{'all':<22}{applied:>9,}{'':>8}{labelled:>10,}")
print(f"labelled, as a share of applications: {labelled / applied:.0%}")
