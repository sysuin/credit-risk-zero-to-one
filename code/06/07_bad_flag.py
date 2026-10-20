# A scorecard's target: personal loans opened 2019-2023, each labelled
# good, indeterminate or bad over its first months on book.
import fernhill

con = fernhill.connect()
con.execute("""
    CREATE TEMP TABLE worst AS
    SELECT a.account_id, w.months,
           max(p.missed) AS worst,
           bool_or(p.status IN ('repaid', 'prepaid')) AS closed
    FROM accounts a
    JOIN performance p USING (account_id)
    CROSS JOIN (SELECT unnest([6, 12, 18, 24]) AS months) w
    WHERE a.product = 'personal'
      AND a.open_date BETWEEN DATE '2019-01-01' AND DATE '2023-12-31'
      AND p.month <= last_day(a.open_date + to_months(w.months))
    GROUP BY ALL""")
n, good, indet, bad, early = con.execute("""
    SELECT count(*), count(*) FILTER (WHERE worst = 0),
           count(*) FILTER (WHERE worst BETWEEN 1 AND 2),
           count(*) FILTER (WHERE worst >= 3),
           count(*) FILTER (WHERE worst = 0 AND closed)
    FROM worst WHERE months = 12""").fetchone()
print(f"personal loans opened 2019-2023: {n:,}; first 12 months:")
for name, k in [("good: never missed a payment", good),
                ("indeterminate: worst 30 or 60 dpd", indet),
                ("bad: reached 90 days past due", bad)]:
    print(f"  {name:<36}{k:>7,}{k / n:>8.2%}")
print(f"  (of the good, closed inside 12 months: {early:,})")
print(f"bad rate excluding indeterminates: "
      f"{bad / (good + bad):.2%}")
print(f"\n{'window':<10}{'bad':>8}{'bad rate':>10}"
      f"{'indeterminate':>15}")
for months, b, i, total in con.execute("""
    SELECT months, count(*) FILTER (WHERE worst >= 3),
           count(*) FILTER (WHERE worst BETWEEN 1 AND 2), count(*)
    FROM worst GROUP BY 1 ORDER BY 1""").fetchall():
    print(f"{months:>2} months{b:>8,}{b / total:>10.2%}"
          f"{i / total:>15.2%}")
