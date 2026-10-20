# Fernhill's own covenants against covenants set with 30% and 50%
# headroom on the same accounts at signing, tested over the same
# facility-years; and how far EBITDA moves in a year.
import fernhill
from _book import accounts, facilities, latest_year, live_years, rates
from ballast.commercial import structure as st

con = fernhill.connect()
acc, fac = accounts(con), facilities(con)
fac["fy0"] = fac.start_date.map(latest_year)
base = fac.merge(acc, left_on=["company_id", "fy0"],
                 right_on=["company_id", "fy"])
base = base[base.ebitda > 0]

print(f"{'covenants':<26}{'last':>7}{'-1 yr':>7}"
      f"{'-2 yrs':>7}{'others':>8}")
for headroom in (None, 0.30, 0.50):
    f = base[["facility_id", "fy0", "cap", "floor"]].copy()
    if headroom:
        lv = [st.covenant_levels(d / e, e / i, headroom=headroom)
              for d, e, i in zip(base.debt, base.ebitda, base.interest)]
        f["cap"], f["floor"] = [a for a, _ in lv], [b for _, b in lv]
    t = live_years(acc, fac[["facility_id", "company_id",
                             "start_date", "maturity_date"]]
                   .merge(f, on="facility_id"))
    t = t[t.fy > t.fy0].reset_index(drop=True)
    t["breach"] = st.breaches(t.debt, t.ebitda, t.interest, t.cap,
                              t.floor).breach
    cy = t.groupby(["company_id", "fy", "k"], dropna=False
                   ).breach.any().reset_index()
    cy["k"] = cy[cy.k.notna()].groupby("company_id").fy.rank(
        ascending=False)
    v = rates(cy)
    label = (f"{headroom:.0%} on own numbers" if headroom
             else "as Fernhill signed them")
    print(f"  {label:<24}" + "".join(f"{x:>7.0%}" for x in v[:3])
          + f"{v[3]:>8.0%}")
print(f"  defaulters tested: {(cy.k == 1).sum()}; other company-"
      f"years: {cy.k.isna().sum()}")

acc["change"] = acc.groupby("company_id").ebitda.pct_change()
print("\nEBITDA, change from one year to the next")
print(f"  {'':<14}{'years':>7}{'p25':>8}{'median':>8}{'p75':>8}"
      f"{'fell 30%+':>11}")
for label, g in (("all sectors", acc),
                 ("wholesale", acc[acc.sector == "wholesale"])):
    ch = g.change.dropna()
    print(f"  {label:<14}{len(ch):>7}{ch.quantile(0.25):>8.1%}"
          f"{ch.median():>8.1%}{ch.quantile(0.75):>8.1%}"
          f"{(ch < -0.30).mean():>11.0%}")
