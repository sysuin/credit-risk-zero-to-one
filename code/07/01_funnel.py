# From every personal-loan application to the loans with an outcome.
import fernhill
from ballast.scorecard import sample

con = fernhill.connect()
rows = con.execute("""
    SELECT CASE WHEN app_date <= ? THEN 'development'
                WHEN app_date <= ? THEN 'out_of_time'
                ELSE 'too_recent' END AS period,
           count(*),
           count(*) FILTER (WHERE outcome = 'declined'),
           count(*) FILTER (WHERE outcome IN ('not_taken_up',
                                              'offer_open')),
           count(*) FILTER (WHERE outcome = 'booked')
    FROM applications WHERE product = 'personal'
    GROUP BY period ORDER BY min(app_date)
""", [sample.DEV_TO, sample.OOT_TO]).fetchall()
print(f"{'period':<13}{'applied':>9}{'declined':>10}{'walked':>8}"
      f"{'booked':>8}")
for period, n, declined, walked, booked in rows:
    print(f"{period:<13}{n:>9,}{declined:>10,}{walked:>8,}"
          f"{booked:>8,}")

# Has each booked loan had all twelve payments fall due (or closed)?
out = sample.outcomes(con)
dates = con.execute("SELECT app_id, app_date FROM applications "
                    "WHERE product = 'personal'").df()
out = out.merge(dates, on="app_id")
out["period"] = sample.period(out["app_date"].dt.date)
print()
print("booked loans whose 12-payment window has finished:")
for period, g in out.groupby("period", sort=False):
    print(f"  {period:<13}{int(g['complete'].sum()):>7,} of "
          f"{len(g):>6,}")
