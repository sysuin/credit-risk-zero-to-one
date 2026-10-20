# Credit line increases on Fernhill's cards: who was eligible at each
# six-monthly review, who got one, and what happened next.
import fernhill
from ballast import performance as perf
from ballast.decision import policy as pol

con = fernhill.connect()
perf.prepare(con)                  # migrated cards stitched to roots
reviews = con.execute(f"""
    WITH r AS (
        SELECT root_id, month, limit_cents, balance_cents,
               datediff('month', root_open, month) AS mob,
               lag(limit_cents) OVER w AS old_limit,
               lag(balance_cents) OVER w AS old_balance,
               lag(missed) OVER w AS old_missed,
               max(missed) OVER (w ROWS BETWEEN 1 FOLLOWING
                                 AND 12 FOLLOWING) AS worst_next,
               lead(balance_cents, 6) OVER w AS balance_6m
        FROM history WHERE product = 'card'
        WINDOW w AS (PARTITION BY root_id ORDER BY month))
    -- The new limit shows on the statement after each six-month
    -- anniversary: months on book 7, 13, 19, ...
    SELECT year(month) AS year, limit_cents > old_limit AS granted,
           worst_next >= 3 AS bad_next,
           balance_6m * 1.0 / old_limit AS drawn_6m
    FROM r
    WHERE mob > 1 AND mob % {pol.CLI_EVERY} = 1 AND old_missed = 0
      AND old_balance > {pol.CLI_MIN_USE} * old_limit
      AND old_limit < {pol.CLI_CAP_CENTS}
    ORDER BY root_id, month""").df()
print("Six-monthly reviews of cards up to date and over half used")
print(f"  {'year':<6}{'eligible':>9}{'granted':>9}{'share':>7}")
for y, g in reviews.groupby("year"):
    print(f"  {y:<6}{len(g):>9,}{int(g['granted'].sum()):>9,}"
          f"{g['granted'].mean():>7.1%}")
done = reviews[reviews["year"] <= 2024]
print("\nReviews 2016-2024, the twelve months after")
print(f"  {'':<12}{'reviews':>9}{'90+ next 12m':>14}"
      f"{'balance at 6m':>15}")
for name, g in (("granted", done[done["granted"]]),
                ("not granted", done[~done["granted"]])):
    print(f"  {name:<12}{len(g):>9,}{g['bad_next'].mean():>14.2%}"
          f"{g['drawn_6m'].median():>15.0%}")
print("balance at 6m: median balance six months on, as a share of"
      "\n  the limit before the review")
