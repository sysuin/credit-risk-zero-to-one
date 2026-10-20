# Fernhill's book as the simulation sees it: retail pools and companies
# by name, reconciled to Chapter 21's saved run.
import fernhill
from ballast import capital, portfolio as pf

con = fernhill.connect()
r = capital.load()
pools, names = pf.book(con, r)
pools["el"] = pools["pd"] * pools.lgd * pools.ead
print(f"{'':<14}{'pools':>6}{'accounts':>9}{'EAD $m':>9}{'PD':>7}"
      f"{'LGD':>7}{'cure':>6}{'EL $m':>7}")
for p, g in pools.groupby("product"):
    print(f"{p:<14}{len(g):>6}{g.accounts.sum():>9,}"
          f"{g.ead.sum() / 1e8:>9,.1f}"
          f"{(g['pd'] * g.ead).sum() / g.ead.sum():>7.2%}"
          f"{g.lgd.iloc[0]:>7.1%}{g.cure_rate.iloc[0]:>6.0%}"
          f"{g.el.sum() / 1e8:>7.2f}")
el_c = (names["pd"] * names.lgd * names.ead).sum()
print(f"{'companies':<14}{'':>6}{len(names):>9,}"
      f"{names.ead.sum() / 1e8:>9,.1f}"
      f"{(names['pd'] * names.ead).sum() / names.ead.sum():>7.2%}"
      f"{(names.lgd * names.ead).sum() / names.ead.sum():>7.1%}"
      f"{'':>6}{el_c / 1e8:>7.2f}")
print(f"expected loss, PD x LGD x EAD: "
      f"${pf.expected_loss(pools, names) / 100:,.0f}")

d = r.in_default.astype(bool)
ret = r[(r.segment == "retail") & ~d]
com = r[r.segment == "commercial"]
print(f"\nretail EAD ${pools.ead.sum() / 100:,.0f}; Chapter 21's "
      f"${ret.irb_ead.sum() / 100:,.0f}")
print(f"companies' EAD, Fernhill's revolver CCF "
      f"${names.ead.sum() / 1e8:,.1f}m;\n  supervisory CCF "
      f"${com.irb_ead.sum() / 1e8:,.1f}m")
print(f"left out, already in default: {d.sum()} exposures, "
      f"${r[d].irb_ead.sum() / 1e8:,.1f}m")
