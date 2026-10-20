# Who the bureau does not know: no-hits and thin files by age.
import json

import fernhill

con = fernhill.connect()
rows = con.execute("""
    SELECT CASE WHEN age < 21 THEN '18-20' WHEN age < 23 THEN '21-22'
                WHEN age < 25 THEN '23-24' WHEN age < 27 THEN '25-26'
                WHEN age < 30 THEN '27-29' WHEN age < 40 THEN '30-39'
                WHEN age < 60 THEN '40-59' ELSE '60+' END AS ages,
           count(*),
           avg((NOT bureau_hit)::INT),
           avg((bureau_hit AND oldest_account_months < 12)::INT),
           avg((bureau_hit AND open_accounts <= 1)::INT)
    FROM applications
    GROUP BY ages ORDER BY ages
""").fetchall()
print(f"{'age':<8}{'applications':>13}{'no hit':>9}{'thin':>8}"
      f"{'0-1 open':>10}")
for ages, n, nohit, thin, few in rows:
    print(f"{ages:<8}{n:>13,}{nohit:>9.1%}{thin:>8.1%}{few:>10.1%}")
total, nohit = con.execute("""
    SELECT count(*), count(*) FILTER (WHERE NOT bureau_hit)
    FROM applications
""").fetchone()
print(f"{'all':<8}{total:>13,}{nohit / total:>9.1%}")

print()
print("no-hit applicants, by age and what Fernhill decided:")
for young, decision, reason, n in con.execute("""
    SELECT age < 25, decision, coalesce(decline_reason, '-'), count(*)
    FROM applications WHERE NOT bureau_hit
    GROUP BY ALL HAVING count(*) >= 100 ORDER BY ALL DESC
""").fetchall():
    ages = "under 25" if young else "25 and over"
    print(f"  {ages:<13}{decision:<9}{reason:<20}{n:>7,}")

with open("code/05/03_no_hits_by_age.json", "w") as f:
    json.dump([{"ages": r[0], "n": r[1], "nohit": r[2], "thin": r[3]}
               for r in rows], f, indent=1)
