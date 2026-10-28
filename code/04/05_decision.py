# The score decides most applications; the refer band goes to people.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

# Applications that passed the policy rules and the fraud check, so
# that the score and the people around it made the decision.
con.execute("""
    CREATE TEMP VIEW scored AS
    SELECT *, mark1_score - cutoff AS gap,
           CASE WHEN mark1_score < cutoff - 10 THEN '1 below refer'
                WHEN mark1_score < cutoff + 10 THEN '2 refer band'
                ELSE '3 above refer' END AS band,
           product IN ('personal', 'card')
             AND app_date BETWEEN DATE '2021-02-01'
                              AND DATE '2022-06-30' AS push
    FROM applications
    WHERE decline_reason IS NULL
       OR decline_reason IN ('score_below_cutoff', 'credit_officer')
""")

# The approval rate in each band. (decision = 'approve')::INT is 1 for
# an approval and 0 otherwise, so its average is the share approved.
print(f"{'score against cut-off':<24}{'apps':>8}{'approved':>10}"
      f"{'low-side':>10}{'high-side':>10}")
rows = con.execute("""
    SELECT band, count(*), avg((decision = 'approve')::INT),
           count(*) FILTER (WHERE override = 'low_side'),
           count(*) FILTER (WHERE override = 'high_side')
    FROM scored GROUP BY band ORDER BY band
""").fetchall()
for band, n, rate, low, high in rows:
    print(f"{band[2:]:<24}{n:>8,}{rate:>10.1%}{low:>10}{high:>10}")

print()
print("refer band, approved")
# The refer band, split into the growth push's instant decisions and
# the applications underwriters read.
split = con.execute("""
    SELECT push, count(*), avg((decision = 'approve')::INT)
    FROM scored WHERE band = '2 refer band'
    GROUP BY push ORDER BY push
""").fetchall()
for push, n, rate in split:
    when = ("growth push, personal and card" if push
            else "every other time")
    print(f"  {when:<32}{n:>8,}{rate:>10.1%}")

# Declines coded "score below cut-off" whose score was not below it.
trap = con.execute("""
    SELECT count(*) FROM applications
    WHERE decline_reason = 'score_below_cutoff'
      AND mark1_score >= cutoff
""").fetchone()[0]
print()
print(f"'score_below_cutoff' with a score at or above the cut-off:"
      f" {trap:,}")

# Approval rate by points from the cut-off, for the figure.
curve = con.execute("""
    SELECT gap, count(*), avg((decision = 'approve')::INT)
    FROM scored WHERE gap BETWEEN -40 AND 39
    GROUP BY gap ORDER BY gap
""").fetchall()
json.dump(curve, open(ROOT / "code/04/05_decision.json", "w"))
