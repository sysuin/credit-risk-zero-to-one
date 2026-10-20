# The LGD and EAD the IRB formula will use: Chapter 19's downturn LGD
# with the floors applied, and EAD against the standardised figure.
import fernhill
from ballast import capital
from ballast.parameters import lgd as lgdm

con = fernhill.connect()
b = capital.standardised(capital.book(con), capital.provisions())
lg = capital.irb_lgd(b)
b["lgd"] = lg.lgd
b["irb_ead"] = capital.irb_ead(b)
p = lgdm.load()["products"]
print(f"{'product':<20}{'Ch 19':>7}{'used':>7}{'SA EAD':>9}"
      f"{'IRB EAD':>9}{'IRB/SA':>8}")
for k, g in b.groupby("product"):
    ch19 = p[k]["downturn"] if k in p else float("nan")
    used = (g.lgd * g.irb_ead).sum() / g.irb_ead.sum()
    sa, ir = g.sa_ead.sum(), g.irb_ead.sum()
    c19 = f"{ch19:>7.1%}" if ch19 == ch19 else f"{'-':>7}"
    print(f"{k:<20}{c19}{used:>7.1%}{sa / 1e8:>9,.1f}{ir / 1e8:>9,.1f}"
          f"{ir / sa:>8.2f}")
print("Ch 19: downturn LGD; used: after floors, the guarantee and the")
print("foundation approach's LGD for companies; EAD in $m")
e = b[b["product"] == "sme_emergency"]
whole = p["sme_emergency"]["downturn"]
print(f"emergency loans: downturn LGD {whole:.1%} of the whole loan,"
      f"\n{e.lgd.iloc[0]:.1%} of the 20% the "
      "guarantee leaves")
