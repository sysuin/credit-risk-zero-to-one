# Fernhill's book as the simulation sees it: retail pools and companies
# by name, reconciled to Chapter 21's saved run.
import fernhill
from ballast import capital, portfolio as pf

con = fernhill.connect()
run = capital.load()                   # Chapter 21's saved run
pools, names = pf.book(con, run)
pools["el"] = pools["pd"] * pools.lgd * pools.ead
print(f"{'':<14}{'pools':>6}{'accounts':>9}{'EAD $m':>9}{'PD':>7}"
      f"{'LGD':>7}{'cure':>6}{'EL $m':>7}")

# One row per retail product; its PD is weighted by exposure.
for product, g in pools.groupby("product"):
    pd_weighted = (g["pd"] * g.ead).sum() / g.ead.sum()
    print(f"{product:<14}{len(g):>6}{g.accounts.sum():>9,}"
          f"{g.ead.sum() / 1e8:>9,.1f}{pd_weighted:>7.2%}"
          f"{g.lgd.iloc[0]:>7.1%}{g.cure_rate.iloc[0]:>6.0%}"
          f"{g.el.sum() / 1e8:>7.2f}")

# One row for the companies, PD and LGD weighted by exposure.
ead_c = names.ead.sum()
el_c = (names["pd"] * names.lgd * names.ead).sum()
pd_c = (names["pd"] * names.ead).sum() / ead_c
lgd_c = (names.lgd * names.ead).sum() / ead_c
print(f"{'companies':<14}{'':>6}{len(names):>9,}{ead_c / 1e8:>9,.1f}"
      f"{pd_c:>7.2%}{lgd_c:>7.1%}{'':>6}{el_c / 1e8:>7.2f}")
print(f"expected loss, PD x LGD x EAD: "
      f"${pf.expected_loss(pools, names) / 100:,.0f}")

# Reconcile with Chapter 21: same retail EAD, other company EAD.
in_default = run.in_default.astype(bool)
retail = run[(run.segment == "retail") & ~in_default]
commercial = run[run.segment == "commercial"]
print(f"\nretail EAD ${pools.ead.sum() / 100:,.0f}; Chapter 21's "
      f"${retail.irb_ead.sum() / 100:,.0f}")
print(f"companies' EAD, Fernhill's revolver CCF "
      f"${ead_c / 1e8:,.1f}m;\n  supervisory CCF "
      f"${commercial.irb_ead.sum() / 1e8:,.1f}m")
print(f"left out, already in default: {in_default.sum()} exposures, "
      f"${run[in_default].irb_ead.sum() / 1e8:,.1f}m")
