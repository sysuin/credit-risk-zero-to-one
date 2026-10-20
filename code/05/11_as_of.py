# Two things in the loan book that were not known when they seem to
# have been: December's outcomes, and what the bureau saw afterwards.
import fernhill

con = fernhill.connect()
print("approved applications, by month applied for, as at 5 Jan 2026")
print(f"{'month':<9}{'approved':>9}{'booked':>8}{'walked':>8}"
      f"{'open':>6}{'take-up':>9}")
for m, n, booked, walked, still in con.execute("""
    SELECT strftime(app_date, '%Y-%m'), count(*),
           count(*) FILTER (WHERE outcome = 'booked'),
           count(*) FILTER (WHERE outcome = 'not_taken_up'),
           count(*) FILTER (WHERE outcome = 'offer_open')
    FROM applications
    WHERE decision = 'approve' AND app_date >= DATE '2025-09-01'
    GROUP BY ALL ORDER BY ALL
""").fetchall():
    print(f"{m:<9}{n:>9,}{booked:>8,}{walked:>8,}{still:>6,}"
          f"{booked / n:>9.1%}")

print()
print("bureau_retro: what the bureau later saw of applicants Fernhill")
print("did not lend to")
print(f"{'applied':<9}{'rows':>8}{'opened elsewhere':>18}"
      f"{'opened within':>14}{'bad known':>11}")
for y, n, opened, latest, bad in con.execute("""
    SELECT year(a.app_date), count(*), avg(r.opened_elsewhere::INT),
           max(r.months_to_open), count(r.bad_12m_elsewhere)
    FROM bureau_retro r JOIN applications a USING (app_id)
    GROUP BY ALL ORDER BY ALL
""").fetchall():
    within = f"{latest} months"
    print(f"{y:<9}{n:>8,}{opened:>18.1%}{within:>14}{bad:>11,}")
