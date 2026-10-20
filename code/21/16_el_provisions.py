# IRB expected loss against the provisions Chapter 20 booked: a
# shortfall comes off CET1, an excess may count as Tier 2, capped.
import fernhill
from ballast import capital

con = fernhill.connect()
r = capital.load()
prov = capital.provisions()
if prov is None:
    print("no provisions saved: expected loss only")
r["prov"] = r.account_id.map(prov.set_index("account_id")["ecl"])
g = r.groupby("product")[["el", "prov"]].sum() / 1e8
print(f"{'$m':<20}{'IRB EL':>8}{'provision':>11}{'gap':>8}")
for p, x in g.iterrows():
    print(f"{p:<20}{x.el:>8.2f}{x.prov:>11.2f}{x.prov - x.el:>8.2f}")
t = g.sum()
print(f"{'all':<20}{t.el:>8.2f}{t.prov:>11.2f}{t.prov - t.el:>8.2f}")
credit = r.irb_rwa.sum()
cap = capital.EXCESS_CAP * credit
print(f"\neverything on IRB: excess ${(t.prov - t.el):,.2f}m;")
print(f"Tier 2 may take {capital.EXCESS_CAP:.1%} of IRB credit RWA, "
      f"${cap / 1e8:,.2f}m")
mg = g.loc["mortgage"]
short = mg.prov < mg.el
print(f"mortgages on IRB: {'shortfall' if short else 'excess'} "
      f"${abs(mg.prov - mg.el):,.2f}m" + (" off CET1" if short else ""))
st = prov.groupby("stage")["ecl"].sum() / 1e8
print("provisions by stage $m: " + ", ".join(
    f"{s} {v:,.2f}" for s, v in st.items()))
