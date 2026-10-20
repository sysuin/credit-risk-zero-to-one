# Fernhill's seven products, sorted by how each is repaid and secured.
import json

import fernhill
from ballast.config import ROOT

con = fernhill.connect()

rows = con.execute("""
    SELECT a.product,
           count(*) AS accounts,
           -- a term means instalments; no term means a credit limit
           bool_and(a.term_months IS NULL) AS revolving,
           avg(coalesce(a.collateral_value_cents > 0, false)::INT)
               AS secured,
           avg(coalesce(s.guarantee = 'government_80pct', false)::INT)
               AS govt,
           string_agg(DISTINCT a.rate_type, ', ' ORDER BY a.rate_type)
               AS rates
    FROM accounts a
    LEFT JOIN sme_applications s ON s.account_id = a.account_id
    GROUP BY a.product
    ORDER BY revolving, secured DESC, a.product
""").fetchall()

print(f"{'product':<14}{'accounts':>8} {'repaid as':<11}"
      f"{'secured':>7} rate")
out = []
for product, n, revolving, secured, govt, rates in rows:
    shape = "revolving" if revolving else "instalment"
    sec = f"{secured:.0%}" if not govt else "guar."
    # fixed_then_variable: fixed for two or five years, then variable
    rates = rates.replace("fixed_then_variable", "resetting")
    print(f"{product:<14}{n:>8,} {shape:<11}{sec:>7} {rates}")
    out.append({"product": product, "revolving": revolving,
                "secured": secured, "guaranteed": govt > 0})

json.dump(out, open(ROOT / "code/03/01_product_map.json", "w"),
          indent=1)
