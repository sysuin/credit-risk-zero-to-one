# Every Fernhill mortgage through the rate rise: payments, then arrears.
import fernhill

con = fernhill.connect()
KINDS = ["fixed", "variable", "fixed_then_variable"]
NAME = {"fixed": "fixed", "variable": "variable",
        "fixed_then_variable": "resetting"}

# Mortgages open at both ends of the rise, December 2021 and 2024,
# with the payment set against the income stated when they applied.
print(f"{'':<22}{'payment rise':>14}{'payment/income':>22}")
print(f"{'open throughout':<16}{'loans':>6}{'median':>8}{'p90':>6}"
      f"{'2021':>10}{'2024':>6}{'2024 p90':>10}")
summary = con.execute("""
    WITH m AS (
        SELECT a.account_id, a.rate_type, x.stated_income_cents AS inc,
               max(p.scheduled_cents)
                   FILTER (WHERE p.month = '2021-12-31') AS before,
               max(p.scheduled_cents)
                   FILTER (WHERE p.month = '2024-12-31') AS after
        FROM accounts a
        JOIN performance p USING (account_id)
        JOIN applications x ON x.account_id = a.account_id
        WHERE a.product = 'mortgage'
        GROUP BY ALL
    )
    SELECT rate_type, count(*),
           median(after / before - 1),
           quantile_cont(after / before - 1, 0.9),
           median(before * 12 / inc), median(after * 12 / inc),
           quantile_cont(after * 12 / inc, 0.9)
    FROM m WHERE before > 0 AND after > 0
    GROUP BY rate_type
""").fetchall()
# Print the kinds in a fixed order: fixed, variable, resetting.
by_kind = {}
for row in summary:
    by_kind[row[0]] = row[1:]
for kind in KINDS:
    n, rise, rise90, pti0, pti1, pti90 = by_kind[kind]
    print(f"{NAME[kind]:<16}{n:>6}{rise:>8.0%}{rise90:>6.0%}"
          f"{pti0:>10.0%}{pti1:>6.0%}{pti90:>10.0%}")

# Did arrears follow? The share of open mortgages behind on a payment
# at a month end, and how many accounts were behind at some point.
rows = con.execute("""
    SELECT year(p.month), a.rate_type,
           avg((p.missed >= 1)::INT),
           count(DISTINCT p.account_id) FILTER (WHERE p.missed >= 1)
    FROM performance p JOIN accounts a USING (account_id)
    WHERE a.product = 'mortgage' AND year(p.month) >= 2019
      AND p.status IN ('up_to_date', 'arrears', 'default')
    GROUP BY ALL ORDER BY ALL
""").fetchall()
cell = {}
for year, kind, share, behind in rows:
    cell[year, kind] = (share, behind)
print()
print("behind at a month end (accounts behind during the year)")
print(f"{'year':<8}{'fixed':>16}{'variable':>16}{'resetting':>16}")
for year in sorted({row[0] for row in rows}):
    line = f"{year:<8}"
    for kind in KINDS:
        share, behind = cell[year, kind]
        line += f"{share:>10.2%} ({behind:>2})"
    print(line)

# The two years after the rise, pooled, against the fixed-rate loans.
pooled = dict(con.execute("""
    SELECT a.rate_type, avg((p.missed >= 1)::INT)
    FROM performance p JOIN accounts a USING (account_id)
    WHERE a.product = 'mortgage' AND year(p.month) IN (2023, 2024)
      AND p.status IN ('up_to_date', 'arrears', 'default')
    GROUP BY a.rate_type
""").fetchall())
line = f"{'2023-24, x fixed':<24}"
for kind in ["variable", "fixed_then_variable"]:
    line += f"{pooled[kind] / pooled['fixed']:>15.1f}x"
print(line)
