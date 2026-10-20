# Fernhill's credit RWA on the IRB approach, account by account, by
# product beside the standardised figure; saved for later chapters.
import json

import fernhill
from ballast import capital

con = fernhill.connect()
r = capital.run(con)
for path in capital.save(r):
    print("saved", path)
g = capital.summary(r)
r["pdw"] = r.pd_floored * r.irb_ead
r["lgdw"] = r.lgd * r.irb_ead
ok = r[~r.in_default]
pw = ok.groupby("product")[["pdw", "lgdw", "irb_ead"]].sum()
print(f"\n{'product':<20}{'PD':>6}{'LGD':>7}{'EAD $m':>9}{'RWA $m':>9}"
      f"{'IRB':>6}{'SA':>6}")
for p, x in g.iterrows():
    q = pw.loc[p]
    print(f"{p:<20}{q.pdw / q.irb_ead:>6.2%}{q.lgdw / q.irb_ead:>7.1%}"
          f"{x.irb_ead / 1e6:>9,.1f}{x.irb_rwa / 1e6:>9,.1f}"
          f"{x.irb_density:>6.0%}{x.sa_density:>6.0%}")
t = g.sum()
print(f"{'all':<20}{'':>13}{t.irb_ead / 1e6:>9,.1f}"
      f"{t.irb_rwa / 1e6:>9,.1f}{t.irb_rwa / t.irb_ead:>6.0%}"
      f"{t.sa_rwa / t.sa_ead:>6.0%}")
print("PD, LGD: performing exposures, weighted by EAD; IRB, SA: RWA")
print("density, each approach's RWA over its own EAD")
print(f"\ncredit RWA: IRB ${t.irb_rwa:,.0f}; standardised "
      f"${t.sa_rwa:,.0f}")
with open("code/21/12_irb.json", "w") as f:
    json.dump({p: [x.sa_rwa / 1e6, x.irb_rwa / 1e6]
               for p, x in g.iterrows()}, f)
