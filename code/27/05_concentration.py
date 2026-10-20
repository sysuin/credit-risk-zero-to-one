# Concentration against the proposed limits: single clients as a
# share of Tier 1, sectors, regions and the mix of the book.
import fernhill
from ballast import appetite as ap
from ballast import ecl

con = fernhill.connect()
cap = ap.capital_now(con)
n = ap.names(con, cap["tier1"])
m = 1e8
print(f"Tier 1 ${cap['tier1'] / m:,.1f}m; limit per client "
      f"{ap.NAME[0]:.0%} (${ap.NAME[0] * cap['tier1'] / m:,.1f}m), "
      f"tolerance {ap.NAME[1]:.0%}")
print(f"\n{'client':<27}{'grade':>5}{'EAD':>7}{'of T1':>7}"
      f"{'SA':>7}{'over':>7}")
for _, r in n.head(8).iterrows():
    over = max(r.ead - ap.NAME[0] * cap["tier1"], 0)
    print(f"{r['name']:<27}{r.grade:>5}{r.ead / m:>7.1f}"
          f"{r.share:>7.1%}{r.sa_share:>7.1%}"
          f"{over / m:>7.1f}".replace("    0.0", "      -"))
big = n[n.share > ap.NAME[0]]
print(f"{len(big)} clients above the limit, ${big.ead.sum() / m:,.1f}m;"
      f" excess ${(big.ead - ap.NAME[0] * cap['tier1']).sum() / m:,.1f}"
      "m")
own = ap.pf.commercial_lgd(con)
hit = ap.NAME[0] * cap["tier1"] * own[True]
pts = hit / cap["sa_rwa"] * 100
print(f"a default at the limit, secured LGD {own[True]:.1%}: "
      f"${hit / m:,.1f}m,")
print(f"  {pts:.2f} points of CET1")
print(f"rules' measure (SA EAD): {(n.sa_share > ap.NAME[0]).sum()} "
      f"above 10%, none above {ap.LARGE_EXPOSURE:.0%}")
top = n.ead.head(10).sum()
print(f"top ten: {top / n.ead.sum():.1%} of commercial "
      f"EAD, {top / cap['tier1']:.0%} of Tier 1")

s = ap.sectors(n)
print(f"\nlargest sector {s.index[0]} {s.iloc[0]:.1%}, smallest "
      f"{s.iloc[-1]:.1%} (limit {ap.SECTOR[0]:.0%})")
rg = ap.regions(con)
print(f"largest region {rg.index[0]} {rg.iloc[0]:.1%}, smallest "
      f"{rg.iloc[-1]:.1%} (limit {ap.REGION[0]:.0%})")
e = ecl.load()
com = e[e.segment == "commercial"].balance_cents.sum()
print(f"commercial {com / e.balance_cents.sum():.1%} of drawn lending "
      f"(limit {ap.COMMERCIAL[0]:.0%}, tolerance "
      f"{ap.COMMERCIAL[1]:.0%})")
w = n[n.grade >= ap.WATCHLIST]
print(f"watchlist (grades 9-10): {len(w)} clients, "
      f"${w.ead.sum() / m:,.1f}m, "
      f"{w.ead.sum() / n.ead.sum():.1%} of EAD")
