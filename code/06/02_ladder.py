# The arrears ladder on 31 December 2025: every open consumer account
# by days past due, as a count and as a share of what is owed.
import fernhill
from ballast.config import AS_OF

con = fernhill.connect()
rows = con.execute("""
    SELECT least(missed, 6) AS rung, count(*) AS n,
           sum(balance_cents) AS owed
    FROM performance
    WHERE month = ? AND status IN ('up_to_date', 'arrears', 'default')
      AND product IN ('personal', 'card', 'auto', 'mortgage')
    GROUP BY rung ORDER BY rung""", [AS_OF]).fetchall()
total_n = sum(r[1] for r in rows)
total_owed = sum(r[2] for r in rows)
names = ["current", "30", "60", "90", "120", "150", "180+"]
print(f"{'days past due':<15}{'accounts':>9}{'share':>8}"
      f"{'owed':>16}{'share':>8}")
for rung, n, owed in rows:
    print(f"{names[rung]:<15}{n:>9,}{n / total_n:>8.2%}"
          f"{owed / 100:>16,.0f}{owed / total_owed:>8.2%}")
print(f"{'all open':<15}{total_n:>9,}{'':>8}{total_owed / 100:>16,.0f}")
behind = sum(r[1] for r in rows if r[0] >= 1)
print(f"30+ days past due: {behind:,} accounts "
      f"({behind / total_n:.2%})")
print("180+ by product:", con.execute("""
    SELECT string_agg(DISTINCT product) FROM performance
    WHERE month = ? AND missed >= 6
      AND status IN ('up_to_date', 'arrears', 'default')
      AND product IN ('personal', 'card', 'auto', 'mortgage')""",
                                      [AS_OF]).fetchone()[0])
