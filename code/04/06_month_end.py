# One month end of servicing: where every open account stood.
import fernhill
from ballast.config import AS_OF

con = fernhill.connect()

# Accounts open at the month end, by how many payments they had missed.
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

# Accounts that closed during the month, by how they closed.
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

# Card limits: each month's limit beside the month before's.
con.execute("""
    CREATE TEMP VIEW card_limits AS
    SELECT account_id, limit_cents,
           lag(limit_cents) OVER (PARTITION BY account_id
                                  ORDER BY month) AS prev
    FROM performance WHERE product = 'card'
""")
# For each card, how many times its limit went up and down.
con.execute("""
    CREATE TEMP VIEW limit_moves AS
    SELECT account_id,
           count(*) FILTER (WHERE limit_cents > prev) AS ups,
           count(*) FILTER (WHERE limit_cents < prev) AS downs
    FROM card_limits GROUP BY account_id
""")
raised, cut, cards = con.execute("""
    SELECT count(*) FILTER (WHERE ups > 0),
           count(*) FILTER (WHERE downs > 0), count(*)
    FROM limit_moves
""").fetchone()
print(f"card accounts: {cards:,}; limit raised on {raised:,},"
      f" cut on {cut:,}")
