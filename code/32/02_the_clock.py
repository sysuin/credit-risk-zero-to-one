# Months on book three ways, and the window that loses a month.
import fernhill

con = fernhill.connect()

checks = [
    ("months, 15 Jan to 31 Jan",
     "date_diff('month', DATE '2023-01-15', DATE '2023-01-31')"),
    ("months, 31 Jan to 28 Feb",
     "date_diff('month', DATE '2023-01-31', DATE '2023-02-28')"),
    ("month end of 10 Feb 2024", "last_day(DATE '2024-02-10')"),
    ("31 Jan 2023 plus a month",
     "CAST(DATE '2023-01-31' + INTERVAL 1 MONTH AS DATE)")]
for label, expr in checks:
    print(f"{label:<26}{con.execute(f'SELECT {expr}').fetchone()[0]}")

con.execute("""
    CREATE TEMP TABLE clock AS
    SELECT a.account_id, a.open_date, p.month, p.missed,
           date_diff('month', a.open_date, p.month) AS mob,
           p.month > a.open_date
             AND p.month <= a.open_date + INTERVAL 12 MONTH
             AS by_interval
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = 'personal'
      AND a.open_date >= DATE '2023-01-01'
      AND a.open_date <  DATE '2023-07-01'""")

windows = con.execute("""
    SELECT 'months on book 1-12' AS rule,
           count(*) FILTER (WHERE mob BETWEEN 1 AND 12),
           count(DISTINCT account_id)
             FILTER (WHERE mob BETWEEN 1 AND 12 AND missed >= 3)
    FROM clock
    UNION ALL
    SELECT 'open date + 12 months',
           count(*) FILTER (WHERE by_interval),
           count(DISTINCT account_id)
             FILTER (WHERE by_interval AND missed >= 3)
    FROM clock
    ORDER BY 1""").fetchall()
month_0, month_12 = con.execute("""
    SELECT count(*) FILTER (WHERE by_interval AND mob = 0),
           count(*) FILTER (WHERE NOT by_interval AND mob = 12)
    FROM clock""").fetchone()

d = con.execute("SELECT * FROM clock").df()
mob = ((d["month"].dt.year - d["open_date"].dt.year) * 12
       + d["month"].dt.month - d["open_date"].dt.month)
w = d[mob.between(1, 12)]

n_loans = d["account_id"].nunique()
print(f"{n_loans:,} personal loans opened Jan-Jun 2023")
print(f"{'window':<24}{'rows':>8}{'ever 90+':>10}")
for rule, n_rows, bads in windows:
    print(f"{rule:<24}{n_rows:>8,}{bads:>10}")
print(f"{'pandas, months on book':<24}{len(w):>8,}"
      f"{w.loc[w['missed'] >= 3, 'account_id'].nunique():>10}")
print(f"the interval adds {month_0:,} rows of month 0 "
      f"and drops {month_12:,} of month 12")
