# What repossessed cars, homes and business assets fetched.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

# Every account whose collateral was sold: what the asset was worth,
# what was lent and owed at default, and what came back afterwards.
WORKOUTS = """
    WITH first_default AS (
        SELECT account_id, arg_min(ead_cents, default_month) AS ead
        FROM defaults GROUP BY account_id
    ),
    came_back AS (
        SELECT account_id,
               sum(amount_cents) FILTER (WHERE kind = 'collateral_sale')
                   AS sale,
               sum(amount_cents) FILTER (WHERE kind = 'cost') AS cost,
               sum(amount_cents)
                   FILTER (WHERE kind = 'collections_payment')
                   AS collected,
               min(month) FILTER (WHERE kind = 'collateral_sale')
                   AS sold
        FROM recoveries GROUP BY account_id
    )
    SELECT a.account_id, a.product, a.open_date, a.close_date,
           a.collateral_value_cents AS value, a.amount_cents AS lent,
           f.ead, c.sale, coalesce(c.cost, 0) AS cost,
           coalesce(c.collected, 0) AS collected, c.sold
    FROM accounts a
    JOIN first_default f USING (account_id)
    JOIN came_back c USING (account_id)
    WHERE c.sale IS NOT NULL
"""
# Medians for each product whose collateral was sold.
LABELS = {"auto": "cars", "mortgage": "homes", "sme_term": "business"}
print(f"{'sold':<10}{'count':>6}{'sale/value':>12}{'sale/owed':>11}"
      f"{'months':>8}{'owed/value':>12}")
for row in con.execute(f"""
    SELECT product, count(*),
           median(sale / value),         -- against the price at opening
           median(sale / ead),           -- against the debt at default
           median(date_diff('month', open_date, sold)),
           median(ead / value)
    FROM ({WORKOUTS}) GROUP BY product ORDER BY product
""").fetchall():
    product, n, sale_value, sale_owed, months, owed_value = row
    print(f"{LABELS[product]:<10}{n:>6}{sale_value:>12.0%}"
          f"{sale_owed:>11.0%}{months:>8.0f}{owed_value:>12.0%}")

# One repossession followed to the end: a workout closed by 2022, so
# its recoveries have had three years to arrive, and the median loss.
one = con.execute(f"""
    WITH w AS (
        SELECT *, (ead - sale - cost - collected) / ead AS lgd
        FROM ({WORKOUTS})
        WHERE product = 'auto' AND close_date <= '2022-12-31'
    )
    SELECT * EXCLUDE (lgd) FROM w
    ORDER BY abs(lgd - (SELECT median(lgd) FROM w)), account_id
    LIMIT 1
""").fetchone()
acc, _, opened, closed, value, lent, ead, sale, cost, coll, _ = one
loss = ead - sale - cost - coll
print()
print(f"{acc}, opened {opened}, repossessed and closed {closed}")
for label, cents in [("price of the car", value), ("lent", lent),
                     ("owed at default", ead), ("car sold for", sale),
                     ("costs", cost), ("collected later", coll),
                     ("loss", loss)]:
    print(f"  {label:<20}{cents / 100:>12,.2f}")
print(f"  {'loss given default':<20}{loss / ead:>12.0%}")

json.dump({"account": acc, "closed": str(closed), "value": value,
           "lent": lent, "ead": ead, "sale": sale, "cost": cost,
           "collected": coll, "loss": loss},
          open(ROOT / "code/03/04_collateral.json", "w"), default=float)
