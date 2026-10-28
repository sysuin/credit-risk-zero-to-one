# The default rate each of Fernhill's personal-loan prices can bear.
import json

import fernhill
from ballast.config import ROOT
from ballast.loanmath import break_even_default_rate

LGD = 0.80     # illustrative: share of a defaulted balance lost
OPEX = 2.5     # illustrative: running costs, % of balance a year
BANDS = """
    CASE WHEN mark1_score >= 660 THEN '660 and up'
         WHEN mark1_score >= 630 THEN '630-659'
         WHEN mark1_score >= 600 THEN '600-629'
         ELSE 'below 600' END
"""

con = fernhill.connect()
cof = con.execute("""
    SELECT cost_of_funds_pct FROM market_rates
    WHERE month = '2025-12-31'
""").fetchone()[0]

# The price tiers, as quoted to approved applicants in December 2025.
tiers = con.execute(f"""
    SELECT {BANDS} AS band, max(offered_rate_pct) AS rate
    FROM applications
    WHERE product = 'personal' AND app_date >= '2025-12-01'
      AND decision = 'approve'
    GROUP BY band ORDER BY rate
""").fetchall()

# What each band actually did: the share of personal loans booked
# April 2019 to December 2024 that were 90 days past due (three
# payments missed) within 12 months of opening. First one row per
# loan, with bad = 1 if it got there; then the average by band.
rates_seen = con.execute(f"""
    WITH loans AS (
        SELECT {BANDS} AS band,
               max(p.missed >= 3 AND p.month <= a.open_date
                   + INTERVAL 12 MONTH)::INT AS bad
        FROM accounts a
        JOIN applications ap USING (account_id)
        JOIN performance p USING (account_id)
        WHERE a.product = 'personal'
          AND a.open_date BETWEEN '2019-04-01' AND '2024-12-31'
        GROUP BY a.account_id, band
    )
    SELECT band, avg(bad) FROM loans GROUP BY band
""").fetchall()
seen = dict(rates_seen)           # look up a band's rate by its name

print(f"cost of funds, December 2025: {cof:.2f}%")
print(f"assumed: LGD {LGD:.0%}, operating cost {OPEX}% a year")
print()
print(f"{'Mark I score':<14}{'price':>7}{'margin':>8}{'break-even':>12}"
      f"{'seen':>7}")
rows = []                         # one per tier, for the figure
for band, rate in tiers:
    margin = rate - cof - OPEX
    even = break_even_default_rate(rate, cof, OPEX, LGD)
    rows.append({"band": band, "rate": rate, "even": even,
                 "seen": seen[band] * 100})
    print(f"{band:<14}{rate:>6.1f}%{margin:>7.2f}%{even:>11.1f}%"
          f"{seen[band]:>7.1%}")


def net_per_100(rate, default):
    """What $100 of balance makes in a year, after every cost."""
    return rate - cof - OPEX - default * LGD


# A risky loan at a high price, and a safe one at a low price.
high = net_per_100(18.0, 5.0)
low = net_per_100(6.0, 2.0)
print()
print(f"price 18.0%, defaults 5% a year: {high:+.2f} per $100 a year")
print(f"price  6.0%, defaults 2% a year: {low:+.2f} per $100 a year")

json.dump({"cof": cof, "lgd": LGD, "opex": OPEX, "tiers": rows},
          open(ROOT / "code/02/09_break_even.json", "w"))
