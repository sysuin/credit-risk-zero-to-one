# One month end of servicing: where every open account stood.
import fernhill
from ballast.config import AS_OF

con = fernhill.connect()

rows = con.execute("""
    SELECT product, count(*),
           count(*) FILTER (WHERE missed = 0),
           count(*) FILTER (WHERE missed = 1),
           count(*) FILTER (WHERE missed = 2),
           count(*) FILTER (WHERE missed >= 3),
           sum(balance_cents)
    FROM performance
    WHERE month = ? AND status IN ('up_to_date', 'arrears', 'default')
    GROUP BY product ORDER BY product
""", [AS_OF]).fetchall()
print(f"open on {AS_OF}")
print(f"{'product':<14}{'open':>7}{'up to date':>11}{'30 days':>8}"
      f"{'60':>5}{'90+':>5}{'balance $m':>12}")
for product, n, ok, d30, d60, d90, bal in rows:
    print(f"{product:<14}{n:>7,}{ok:>11,}{d30:>8}{d60:>5}{d90:>5}"
          f"{bal / 100 / 1e6:>12,.1f}")
n = sum(r[1] for r in rows)
behind = sum(r[1] - r[2] for r in rows)
print(f"{'all':<14}{n:>7,}   behind: {behind:,} ({behind / n:.1%})")

print()
closed = con.execute("""
    SELECT status, count(*) FROM performance
    WHERE month = ?
      AND status NOT IN ('up_to_date', 'arrears', 'default')
    GROUP BY status ORDER BY count(*) DESC, status
""", [AS_OF]).fetchall()
print("closed during the month")
for status, k in closed:
    print(f"  {status.replace('_', ' '):<22}{k:>5}")

changed = con.execute("""
    SELECT count(*) FILTER (WHERE ups > 0),
           count(*) FILTER (WHERE downs > 0), count(*)
    FROM (SELECT account_id,
                 count(*) FILTER (WHERE limit_cents > prev) AS ups,
                 count(*) FILTER (WHERE limit_cents < prev) AS downs
          FROM (SELECT account_id, limit_cents,
                       lag(limit_cents) OVER (PARTITION BY account_id
                                              ORDER BY month) AS prev
                FROM performance WHERE product = 'card')
          GROUP BY account_id)
""").fetchone()
print(f"card accounts: {changed[2]:,}; limit raised on {changed[0]:,},"
      f" cut on {changed[1]:,}")
