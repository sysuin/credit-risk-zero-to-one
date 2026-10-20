# How long a card or an overdraft lives at Fernhill, and what the
# choice of behavioural life does to the stage 2 provision on cards.
# timeout: 300
import fernhill
from ballast import ecl
from ballast import performance as perf

con = fernhill.connect()
perf.prepare(con)
print("still open, of those open on 31 December 2020")
print(f"{'':<14}" + "".join(f"{y:>8}" for y in range(2021, 2026)))
for p in ecl.REVOLVING:
    rows = con.execute("""
        WITH s AS (SELECT root_id FROM history
                   WHERE product = ? AND month = DATE '2020-12-31'
                     AND status IN ('up_to_date', 'arrears'))
        SELECT year(month), count(DISTINCT root_id)
        FROM history JOIN s USING (root_id)
        WHERE month(month) = 12 AND year(month) >= 2020
          AND status IN ('up_to_date', 'arrears', 'default')
        GROUP BY 1 ORDER BY 1""", [p]).fetchall()
    n0 = rows[0][1]
    print(f"{p:<14}" + "".join(f"{n / n0:>8.0%}" for _, n in rows[1:]))

params = ecl.parameters(con)
print(f"\n{'card life':<14}{'stage 2':>9}{'stage 2 ECL':>13}"
      f"{'all cards':>11}")
for life in (24, 36, 60, 120):
    ecl.LIFE["card"] = life
    r = ecl.run(con, ecl.AS_OF, params)
    c = r[r["product"] == "card"]
    two = c["stage"] == 2
    print(f"{life:>4} months{'':<4}{two.sum():>9,}"
          f"{c.loc[two, 'ecl'].sum() / 1e8:>12.2f}m"
          f"{c['ecl'].sum() / 1e8:>10.2f}m")
