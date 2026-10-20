# The 2020 payment holidays: who took one, what their days past due
# showed while it ran, and what showed once it ended.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()
n, three, six, first, last = con.execute("""
    SELECT count(DISTINCT account_id),
           count(*) FILTER (WHERE detail = 3),
           count(*) FILTER (WHERE detail = 6),
           min(event_date), max(event_date)
    FROM account_events WHERE event = 'payment_holiday_start'
""").fetchone()
print(f"holidays: {n:,} accounts ({three:,} of 3 months, "
      f"{six:,} of 6),\n  starting {first:%b %Y} to {last:%b %Y}")
rows, most_missed, most_due = con.execute("""
    SELECT count(*), max(missed), max(scheduled_cents)
    FROM performance WHERE payment_holiday""").fetchone()
print(f"month ends on holiday: {rows:,}; most missed {most_missed}; "
      f"most due ${most_due / 100:,.0f}")

# Everyone who could have asked: open, up to date and with a payment
# due at the end of March 2020. Did they take a holiday, and how did
# they pay from October 2020 to September 2021?
con.execute("""
    CREATE TEMP TABLE pool AS
    SELECT p.account_id, p.product,
           h.account_id IS NOT NULL AS holiday
    FROM performance p
    LEFT JOIN (SELECT DISTINCT account_id FROM account_events
               WHERE event = 'payment_holiday_start') h
      USING (account_id)
    WHERE p.month = DATE '2020-03-31' AND p.missed = 0
      AND p.status = 'up_to_date' AND p.scheduled_cents > 0
      AND p.product IN ('personal', 'card', 'auto', 'mortgage')""")
rows = con.execute("""
    SELECT k.holiday, count(DISTINCT k.account_id) AS n,
           count(DISTINCT p.account_id) FILTER (
               WHERE p.month <= DATE '2020-09-30'
                 AND p.missed >= 1) AS missed_during,
           count(DISTINCT p.account_id) FILTER (
               WHERE p.month > DATE '2020-09-30'
                 AND p.missed >= 1) AS missed_after,
           count(DISTINCT p.account_id) FILTER (
               WHERE p.month > DATE '2020-09-30'
                 AND p.missed >= 3) AS dpd90_after
    FROM pool k JOIN performance p USING (account_id)
    WHERE p.month BETWEEN DATE '2020-04-30' AND DATE '2021-09-30'
    GROUP BY 1 ORDER BY 1 DESC""").fetchall()
print(f"\n{'up to date, Mar 2020':<22}{'accounts':>9}"
      f"{'missed':>9}{'missed':>9}{'90+':>9}")
print(f"{'':<22}{'':>9}{'Apr-Sep':>9}{'after':>9}{'after':>9}")
for hol, n, d, a, b in rows:
    name = "took a holiday" if hol else "did not"
    print(f"{name:<22}{n:>9,}{d / n:>9.1%}{a / n:>9.1%}{b / n:>9.1%}")

# Month by month: the share of each group 30+ days past due.
series = con.execute("""
    SELECT p.month, k.holiday,
           avg((p.missed >= 1)::INT) AS behind
    FROM pool k JOIN performance p USING (account_id)
    WHERE p.month BETWEEN DATE '2019-10-31' AND DATE '2021-12-31'
      AND p.status IN ('up_to_date', 'arrears', 'default')
    GROUP BY ALL ORDER BY ALL""").fetchall()
json.dump([{"month": str(m), "holiday": h, "behind": b}
           for m, h, b in series],
          open(ROOT / "code/06/06_holidays.json", "w"))
show = {"2019-10-31", "2020-02-29", "2020-06-30", "2020-08-31",
        "2021-01-31", "2021-06-30", "2021-12-31"}
share = {(str(m), h): b for m, h, b in series}
print(f"\n{'30+ dpd at':<12}{'took a holiday':>16}{'did not':>10}")
for m in sorted(show):
    print(f"{m:<12}{share[m, True]:>16.2%}{share[m, False]:>10.2%}")
