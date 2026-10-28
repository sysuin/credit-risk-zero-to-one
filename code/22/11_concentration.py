# Concentration: the largest companies, the HHI and the effective
# number of names, sectors, and the retail book's regions.
import json

import fernhill
import numpy as np
from ballast import capital, portfolio as pf
from ballast.config import ROOT

con = fernhill.connect()
run = capital.load()
pools, names = pf.book(con, run)
cap = capital.bank_capital(con)
tier1 = cap["cet1"] + cap["at1"]
info = dict(con.execute("SELECT company_id, name FROM companies")
            .fetchall())

# The companies, largest exposure first.
ranked = names.sort_values("ead", ascending=False)
ranked = ranked.reset_index(drop=True)
total = ranked.ead.sum()
print(f"{'':<4}{'company':<26}{'grade':>5}{'EAD $m':>8}{'share':>7}"
      f"{'of T1':>7}")
for i, row in ranked.head(8).iterrows():
    print(f"{i + 1:<4}{info[row.company_id]:<26}{row.grade:>5.0f}"
          f"{row.ead / 1e8:>8.1f}{row.ead / total:>7.1%}"
          f"{row.ead / tier1:>7.1%}")
top10, top20 = ranked.ead[:10].sum(), ranked.ead[:20].sum()
print(f"top 10 {top10 / total:.1%} of companies' EAD, "
      f"top 20 {top20 / total:.1%}")
print(f"HHI {pf.hhi(ranked.ead):.4f}: as concentrated as "
      f"{pf.effective_number(ranked.ead):.0f} equal names "
      f"(of {len(ranked)})")
meridian = 1_700_000_000                    # the $17m facility
rank = int((ranked.ead > meridian).sum()) + 1
print(f"Meridian's $17m would rank {rank} of {len(ranked) + 1}, "
      f"{meridian / (total + meridian):.2%} of EAD, "
      f"{meridian / tier1:.1%} of Tier 1")

# Sectors: each one's share of the companies' EAD.
sec = ranked.groupby("sector").ead.sum().sort_values(ascending=False)
print(f"\nsectors: largest {sec.index[0]} {sec.iloc[0] / total:.1%}, "
      f"smallest {sec.index[-1]} {sec.iloc[-1] / total:.1%};\n"
      f"  effective number {pf.effective_number(sec):.1f} "
      f"of {len(sec)}")

# Regions: the retail accounts not in default, by region.
retail = run[(run.segment == "retail") & ~run.in_default.astype(bool)]
regions = con.execute("SELECT account_id, region FROM accounts").df()
retail = retail.merge(regions, on="account_id")
by_region = retail.groupby("region").irb_ead.sum()
by_region = by_region.sort_values(ascending=False)
region_total = by_region.sum()
shares = [f"{k} {v / region_total:.0%}" for k, v in by_region.items()]
print("retail regions: " + ", ".join(shares[:3]) + ",\n  "
      + ", ".join(shares[3:]))
print(f"  effective number {pf.effective_number(by_region):.1f} "
      f"of {len(by_region)}")

# The whole book: every company and every retail account.
retail_ead = retail.irb_ead.sum()
everyone = np.r_[ranked.ead, retail.irb_ead]
print(f"whole book: companies {total / (total + retail_ead):.0%} of "
      f"EAD; effective number of exposures "
      f"{pf.effective_number(everyone):.0f}")

json.dump({"ead": (ranked.ead / 1e8).tolist(),
           "meridian": meridian / 1e8, "rank": rank},
          open(ROOT / "code/22/11_concentration.json", "w"))
