# How often each product goes bad, and how much is lost when it does.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

# A card that moved processor in March 2022 is one card under two ids;
# follow it under its first id (Chapter 6 does this properly).
con.execute("""
    CREATE TEMP TABLE fam AS
    SELECT account_id, coalesce(predecessor_id, account_id) AS family
    FROM accounts
""")

# Frequency: of the accounts opened 2016-2022, the share that reached
# 90 days past due (three missed payments) within three years.
freq = con.execute("""
    WITH f AS (
        SELECT fam.family, min(a.open_date) AS opened,
               any_value(a.product) AS product
        FROM accounts a JOIN fam USING (account_id)
        GROUP BY fam.family
    ),
    hit AS (
        SELECT fam.family, min(p.month) AS first90
        FROM performance p JOIN fam USING (account_id)
        WHERE p.missed >= 3
        GROUP BY fam.family
    ),
    lost AS (
        SELECT DISTINCT fam.family
        FROM accounts a JOIN fam USING (account_id)
        WHERE a.close_reason IN ('charged_off', 'vehicle_repossessed',
                                 'property_sold', 'collateral_sold')
    )
    SELECT f.product, count(*),
           avg(coalesce(date_diff('month', f.opened, h.first90) <= 36,
                        false)::INT),
           -- of those reaching 90+, the share later closed at a loss
           avg((l.family IS NOT NULL)::INT)
               FILTER (WHERE h.first90 IS NOT NULL)
    FROM f LEFT JOIN hit h USING (family)
    LEFT JOIN lost l USING (family)
    WHERE year(f.opened) BETWEEN 2016 AND 2022
    GROUP BY f.product
""").fetchall()

# Severity: for workouts that closed at a loss, what was owed at the
# last default against everything recovered afterwards, net of costs.
WORKOUTS = """
    WITH w AS (
        SELECT fam.family, a.product, a.close_date
        FROM accounts a JOIN fam USING (account_id)
        WHERE a.close_reason IN ('charged_off', 'vehicle_repossessed',
                                 'property_sold', 'collateral_sold')
    ),
    d AS (
        SELECT fam.family, d.default_month, d.ead_cents
        FROM defaults d JOIN fam USING (account_id)
    ),
    r AS (
        SELECT fam.family, sum(r.amount_cents) AS net
        FROM recoveries r JOIN fam USING (account_id)
        GROUP BY fam.family
    )
    SELECT w.product, w.close_date,
           arg_max(d.ead_cents, d.default_month) AS ead,
           coalesce(any_value(r.net), 0) AS net
    FROM w JOIN d ON d.family = w.family
                 AND d.default_month <= w.close_date
    LEFT JOIN r ON r.family = w.family
    GROUP BY w.family, w.product, w.close_date
"""
sev = {}
for era, cond in [("old", "close_date <= '2022-12-31'"),
                  ("new", "close_date >= '2024-01-01'")]:
    for p, n, ead, raw, capped in con.execute(f"""
        SELECT product, count(*), sum(ead),
               sum(ead - net),                 -- as recorded
               sum(greatest(ead - net, 0))     -- surplus returned
        FROM ({WORKOUTS}) WHERE {cond}
        GROUP BY product
    """).fetchall():
        sev[p, era] = (n, raw / ead, capped / ead)


def expected_loss(row):
    """Frequency times mature severity, used to sort the products."""
    product, _, frequency, _ = row
    return frequency * sev[product, "old"][2]


# The products from the largest expected loss to the smallest.
order = sorted(freq, key=expected_loss, reverse=True)
print(f"{'':<14}{'opened 2016-22':>16}{'closed by 2022':>20}"
      f"{'2024-25':>10}")
print(f"{'product':<14}{'accounts':>8}{'90+':>8}{'lost':>7}"
      f"{'workouts':>9}{'severity':>10}{'severity':>10}")
for p, n, f90, lost in order:
    workouts, _, mature = sev[p, "old"]
    recent = sev[p, "new"][2]
    print(f"{p:<14}{n:>8,}{f90:>8.1%}{lost:>7.0%}{workouts:>9,}"
          f"{mature:>10.0%}{recent:>10.0%}")

print()
print("Severity as the recoveries table records it, closed by 2022")
for p in ("auto", "mortgage"):
    n, raw, capped = sev[p, "old"]
    print(f"  {p:<10}{raw:>8.0%}   with any surplus returned"
          f"{capped:>6.0%}")

json.dump([{"product": p, "freq": f90, "severity": sev[p, "old"][2],
            "workouts": sev[p, "old"][0]} for p, _, f90, _ in order],
          open(ROOT / "code/03/08_frequency_severity.json", "w"),
          indent=1)
