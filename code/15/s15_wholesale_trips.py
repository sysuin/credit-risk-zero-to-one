# Exercise 15.3: Meridian's pair of covenants (3.25x, 4.00x) on
# Fernhill's wholesale clients, against the whole book.
import fernhill
from ballast.commercial import structure as st

con = fernhill.connect()
acc = con.execute("""
    SELECT f.company_id, c.sector, f.fiscal_year AS fy,
           f.total_debt_cents AS debt, f.ebitda_cents AS ebitda,
           f.interest_cents AS interest, d.default_month AS dm
    FROM financials f JOIN companies c USING (company_id)
    LEFT JOIN corporate_defaults d USING (company_id)
    WHERE c.client_since IS NOT NULL
      AND (d.default_month IS NULL
           OR make_date(f.fiscal_year + 1, 3, 31) < d.default_month)
    ORDER BY 1, 3""").df()
acc["breach"] = st.breaches(acc.debt, acc.ebitda, acc.interest,
                            3.25, 4.00).breach
acc["k"] = acc[acc.dm.notna()].groupby("company_id").fy.rank(
    ascending=False)
print(f"{'either covenant breached':<26}{'last':>7}{'-1 yr':>7}"
      f"{'-2 yrs':>7}{'others':>8}{'n def':>7}")
for label, g in (("whole book", acc),
                 ("wholesale", acc[acc.sector == "wholesale"])):
    cells = [g[g.k == k].breach.mean() for k in (1, 2, 3)]
    cells.append(g[g.dm.isna()].breach.mean())
    print(f"  {label:<24}" + "".join(f"{v:>7.0%}" for v in cells[:3])
          + f"{cells[3]:>8.0%}{(g.k == 1).sum():>7}")
