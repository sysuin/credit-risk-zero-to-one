# Exercise 21.1: the whole book on IRB with Basel II's 1.06 scaling
# factor, and what it does to Fernhill's CET1 ratio.
import fernhill
from ballast import capital

con = fernhill.connect()
r = capital.load()
k = capital.bank_capital(con)
other = k["operational_rwa"] + k["market_rwa"]
prov = capital.provisions().set_index("account_id")["ecl"]
gap = (r.account_id.map(prov).fillna(0) - r.el).sum()
sa = r.sa_rwa.sum() + other
for s in (1.0, 1.06):
    x = capital.irb(r, scaling=s)
    total = capital.output_floor(x.irb_rwa.sum() + other, sa)
    rat = capital.ratios(k, total, gap, x.irb_rwa.sum())
    print(f"scaling {s:.2f}: credit RWA ${x.irb_rwa.sum() / 1e8:,.0f}m,"
          f" total ${total / 1e8:,.0f}m, CET1 {rat['cet1']:.2%}")
print(f"standardised: CET1 {k['cet1'] / sa:.2%}")
