# The default point from the accounts: borrowings split into due
# within a year and due later (Chapter 14's spread), then short-term
# debt plus half of long-term debt.
import fernhill
from ballast import market as mk

con = fernhill.connect()
dp = mk.default_points(con)
cid = con.execute("SELECT company_id FROM companies "
                  "WHERE name = 'Alder Oak Materials'").fetchone()[0]
print(f"Alder Oak Materials, $m    {'short':>7}{'long':>7}"
      f"{'total':>7}{'default':>9}")
print(f"{'accounts  in use from':<27}{'term':>7}{'term':>7}"
      f"{'debt':>7}{'point':>9}")
for r in dp[dp.company_id == cid].itertuples():
    print(f"FY{r.fiscal_year}    {r.available:%d %b %Y}       "
          f"{r.short_term_debt / 1e8:>7.2f}"
          f"{r.long_term_debt / 1e8:>7.2f}{r.total_debt / 1e8:>7.2f}"
          f"{r.default_point / 1e8:>9.2f}")

print(f"\nevery listed client's accounts: {len(dp):,} company-years,"
      f" {dp.company_id.nunique()} companies")
st_share = dp.short_term_debt / dp.total_debt
dp_share = dp.default_point / dp.total_debt
for label, s in (("short-term share of debt", st_share),
                 ("default point / total debt", dp_share)):
    q = s.quantile([0.1, 0.5, 0.9])
    print(f"  {label:<28} p10 {q[0.1]:.0%}  median "
          f"{q[0.5]:.0%}  p90 {q[0.9]:.0%}")
