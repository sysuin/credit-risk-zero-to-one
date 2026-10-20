# Latent quality z against what Fernhill could see (reads the truth).
import fernhill
from ballast.config import TRUTH

con = fernhill.connect()
con.execute(f"ATTACH '{TRUTH}' AS truth (READ_ONLY)")
rows = con.execute("""
    SELECT CASE WHEN z < -1.5 THEN 1 WHEN z < -0.5 THEN 2
                WHEN z < 0.5 THEN 3 WHEN z < 1.5 THEN 4 ELSE 5 END band,
           count(*) n,
           avg(bureau_score) FILTER (WHERE bureau_version = 'v3') v3,
           median(stated_income_cents) / 100 income,
           avg((decision = 'approve')::int) approved,
           avg((outcome = 'booked')::int)
               FILTER (WHERE decision = 'approve') took,
           avg(o.pd12_at_open) pd12
    FROM applications a JOIN truth.applicants t USING (app_id)
    LEFT JOIN truth.origination o USING (app_id)
    WHERE a.product = 'personal' AND NOT t.fraud
    GROUP BY 1 ORDER BY 1""").fetchall()
label = {1: "below -1.5", 2: "-1.5 to -0.5", 3: "-0.5 to 0.5",
         4: "0.5 to 1.5", 5: "above 1.5"}
print("personal-loan applicants, 2016-2025, frauds left out")
print(f"{'z':<13}{'apps':>7}{'bureau v3':>10}{'income':>9}"
      f"{'approved':>9}{'took':>7}{'true PD':>9}")
for b, n, v3, inc, ap, took, pd in rows:
    print(f"{label[b]:<13}{n:>7,}{v3:>10.0f}{inc:>9,.0f}"
          f"{ap:>9.1%}{took:>7.1%}{pd:>9.2%}")
r = con.execute("""
    SELECT corr(z, bureau_score) FILTER (WHERE bureau_version = 'v3'),
           corr(z, mark1_score),
           corr(z, ln(true_income_cents))
    FROM applications JOIN truth.applicants USING (app_id)
    WHERE product = 'personal' AND NOT fraud""").fetchone()
print(f"correlation with z: bureau score {r[0]:.2f}, "
      f"Mark I {r[1]:.2f},")
print(f"  log of true income {r[2]:.2f}")
print()
pair = con.execute("""
    WITH s AS (SELECT a.*, t.z, t.true_income_cents FROM applications a
               JOIN truth.applicants t USING (app_id)
               WHERE product = 'personal' AND year(app_date) = 2025
                 AND mark1_score = 600 AND bureau_hit
                 AND NOT t.fraud)
    (SELECT * FROM s ORDER BY z LIMIT 1)
    UNION ALL (SELECT * FROM s ORDER BY z DESC LIMIT 1)""").df()
print("two 2025 applicants on the same Mark I score, 600")
fields = [("app_id", "{}"), ("z", "{:.2f}"), ("age", "{}"),
          ("bureau_score", "{}"), ("revolving_utilisation", "{:.2f}"),
          ("enquiries_6m", "{}"), ("worst_status_24m", "{}"),
          ("stated_income_cents", "${:,.0f}"),
          ("true_income_cents", "${:,.0f}"), ("decision", "{}"),
          ("offered_rate_pct", "{:.1f}%"), ("outcome", "{}")]
for f, fmt in fields:
    vals = [pair[f].iat[0], pair[f].iat[1]]
    if f.endswith("_cents"):
        vals = [v / 100 for v in vals]
    name = f.replace("_cents", "")
    a, b = (fmt.format(v) for v in vals)
    print(f"  {name:<24}{a:>16}{b:>16}")
