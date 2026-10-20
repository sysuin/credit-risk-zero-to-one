# Fernhill's credit RWA at 31 December 2025 on the standardised
# approach, by product, with defaulted loans and the guarantee.
import fernhill
from ballast import capital

con = fernhill.connect()
prov = capital.provisions()
print("Chapter 20's provisions:", "found" if prov is not None
      else "not found")
s = capital.standardised(capital.book(con), prov)
g = s.groupby("product")[["drawn_cents", "sa_ead", "sa_rwa"]].sum()
print(f"{'product':<20}{'drawn $m':>10}{'EAD $m':>9}{'RWA $m':>9}"
      f"{'density':>9}")
for p, r in g.iterrows():
    print(f"{p:<20}{r.drawn_cents / 1e8:>10,.1f}{r.sa_ead / 1e8:>9,.1f}"
          f"{r.sa_rwa / 1e8:>9,.1f}{r.sa_rwa / r.sa_ead:>9.1%}")
t = g.sum()
print(f"{'all':<20}{t.drawn_cents / 1e8:>10,.1f}{t.sa_ead / 1e8:>9,.1f}"
      f"{t.sa_rwa / 1e8:>9,.1f}{t.sa_rwa / t.sa_ead:>9.1%}")
d = s[s.in_default]
print(f"\nin default: {len(d)} exposures, "
      f"${d.drawn_cents.sum() / 100:,.0f} drawn, "
      f"RWA ${d.sa_rwa.sum() / 100:,.0f}")
base = (d.sa_rw / (1 - d.guaranteed)).round(2)
for rw, n in base.value_counts().sort_index().items():
    print(f"  at {rw:.0%}: {n}")
e = s[s["product"] == "sme_emergency"]
print(f"emergency loans: ${e.sa_ead.sum() / 100:,.0f} EAD, weight "
      f"{e.sa_rwa.sum() / e.sa_ead.sum():.0%} after the guarantee")
print(f"credit RWA, standardised: ${t.sa_rwa / 100:,.0f}")
