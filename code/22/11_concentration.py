# Concentration: the largest companies, the HHI and the effective
# number of names, sectors, and the retail book's regions.
import json

import fernhill
import numpy as np
from ballast import capital, portfolio as pf
from ballast.config import ROOT

con = fernhill.connect()
r = capital.load()
pools, names = pf.book(con, r)
cap = capital.bank_capital(con)
tier1 = cap["cet1"] + cap["at1"]
info = dict(con.execute("SELECT company_id, name FROM companies")
            .fetchall())
n = names.sort_values("ead", ascending=False).reset_index(drop=True)
tot = n.ead.sum()
print(f"{'':<4}{'company':<26}{'grade':>5}{'EAD $m':>8}{'share':>7}"
      f"{'of T1':>7}")
for i, row in n.head(8).iterrows():
    print(f"{i + 1:<4}{info[row.company_id]:<26}{row.grade:>5.0f}"
          f"{row.ead / 1e8:>8.1f}{row.ead / tot:>7.1%}"
          f"{row.ead / tier1:>7.1%}")
print(f"top 10 {n.ead[:10].sum() / tot:.1%} of companies' EAD, "
      f"top 20 {n.ead[:20].sum() / tot:.1%}")
print(f"HHI {pf.hhi(n.ead):.4f}: as concentrated as "
      f"{pf.effective_number(n.ead):.0f} equal names (of {len(n)})")
meridian = 1_700_000_000                    # the $17m facility
rank = int((n.ead > meridian).sum()) + 1
print(f"Meridian's $17m would rank {rank} of {len(n) + 1}, "
      f"{meridian / (tot + meridian):.2%} of EAD, "
      f"{meridian / tier1:.1%} of Tier 1")

sec = n.groupby("sector").ead.sum().sort_values(ascending=False)
print(f"\nsectors: largest {sec.index[0]} {sec.iloc[0] / tot:.1%}, "
      f"smallest {sec.index[-1]} {sec.iloc[-1] / tot:.1%};\n"
      f"  effective number {pf.effective_number(sec):.1f} "
      f"of {len(sec)}")
ret = r[(r.segment == "retail") & ~r.in_default.astype(bool)]
reg = con.execute("SELECT account_id, region FROM accounts").df()
ret = ret.merge(reg, on="account_id")
g = ret.groupby("region").irb_ead.sum().sort_values(ascending=False)
shares = [f"{k} {v / g.sum():.0%}" for k, v in g.items()]
print("retail regions: " + ", ".join(shares[:3]) + ",\n  "
      + ", ".join(shares[3:]))
print(f"  effective number {pf.effective_number(g):.1f} of {len(g)}")
retail = ret.irb_ead.sum()
print(f"whole book: companies {tot / (tot + retail):.0%} of EAD; "
      f"effective number of exposures "
      f"{pf.effective_number(np.r_[n.ead, ret.irb_ead]):.0f}")

json.dump({"ead": (n.ead / 1e8).tolist(), "meridian": meridian / 1e8,
           "rank": rank},
          open(ROOT / "code/22/11_concentration.json", "w"))
