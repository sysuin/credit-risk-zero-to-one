# Exercise 17.3: the spread Merton's model puts on Alder Oak's debt,
# against the margins Fernhill was charging it.
import datetime as dt

import fernhill
from ballast import market as mk

con = fernhill.connect()
cid = con.execute("SELECT company_id FROM companies "
                  "WHERE name = 'Alder Oak Materials'").fetchone()[0]
p = mk.merton_panel(con)
a = p[p.company_id == cid].set_index("month")
print(f"{'month end':<11}{'DD':>6}{'PD':>8}{'Merton spread, bp':>19}")
for day in (dt.date(2019, 3, 31), dt.date(2020, 3, 31),
            dt.date(2020, 9, 30), dt.date(2020, 10, 31)):
    r = a.loc[day]
    bp = mk.merton_spread_bps(r.assets, r.sigma_a, r.default_point,
                              r.r)
    print(f"{day:%b %Y}{r.dd:>9.2f}{r.pd:>8.1%}{bp:>19,.0f}")
print("\nFernhill's facilities")
for fid, kind, start, margin, secured in con.execute("""
        SELECT facility_id, kind, start_date, margin_bps, secured
        FROM facilities WHERE company_id = ? ORDER BY 1""",
        [cid]).fetchall():
    sec = "secured" if secured else "unsecured"
    print(f"  {fid:<12}{kind:<9}{start:%b %Y}  {margin} bp, {sec}")
