# December's arrears by product in SQL, pandas and NumPy, to the cent.
import numpy as np

import fernhill
from ballast.config import AS_OF

con = fernhill.connect()

sql = con.execute("""
    SELECT product,
           count(*) AS accounts,
           count(*) FILTER (WHERE days_past_due >= 30) AS behind,
           coalesce(sum(balance_cents)
                    FILTER (WHERE days_past_due >= 30), 0) AS cents
    FROM performance
    WHERE month = ?
    GROUP BY ALL ORDER BY ALL""", [AS_OF]).fetchall()

rows = con.execute("""
    SELECT product, balance_cents, days_past_due
    FROM performance WHERE month = ?""", [AS_OF]).df()
behind = rows[rows["days_past_due"] >= 30]
by_pandas = (behind.groupby("product")["balance_cents"].sum()
             .reindex([r[0] for r in sql], fill_value=0))

names, code = np.unique(rows["product"].to_numpy(), return_inverse=True)
cents = np.zeros(len(names), dtype=np.int64)
late = rows["days_past_due"].to_numpy() >= 30
np.add.at(cents, code[late], rows["balance_cents"].to_numpy()[late])

print(f"{'product':<15}{'accounts':>9}{'30+ dpd':>9}{'share':>8}"
      f"{'balance 30+':>16}")
for product, accounts, n_behind, c in sql:
    print(f"{product:<15}{accounts:>9,}{n_behind:>9,}"
          f"{n_behind / accounts:>8.2%}{f'${c / 100:,.2f}':>16}")
total = sum(r[3] for r in sql)
print(f"{'all':<15}{len(rows):>9,}{len(behind):>9,}"
      f"{len(behind) / len(rows):>8.2%}{f'${total / 100:,.2f}':>16}")
print("pandas agrees:", by_pandas.tolist() == [r[3] for r in sql])
print("NumPy agrees: ", cents.tolist() == [r[3] for r in sql])

# Divide first, sum second: every month's balances, two ways.
exact, early = con.execute("""
    SELECT sum(balance_cents), sum(balance_cents / 100)
    FROM performance""").fetchone()
print(f"summed in cents:   ${exact / 100:,.2f}")
print(f"divided, summed:   ${early:,.2f}")
