# Chapter 12 held capital at 10% of every personal loan's balance.
# The capital the rules ask for, at the ratio Fernhill holds, by
# product and by personal-loan band.
import fernhill
from ballast import capital

con = fernhill.connect()
r = capital.load()
k = capital.bank_capital(con)
sa = capital.credit_rwa(r) + k["operational_rwa"] + k["market_rwa"]
held = k["cet1"] / sa
print(f"CET1 held per dollar of RWA: {held:.1%} (standardised)")
ok = r[~r.in_default & (r.drawn_cents > 0)]
print("\nCET1 as a share of the balance")
print(f"{'product':<20}{'standardised':>13}{'IRB':>8}")
for p, g in ok.groupby("product"):
    d = g.drawn_cents.sum()
    print(f"{p:<20}{g.sa_rwa.sum() / d * held:>13.1%}"
          f"{g.irb_rwa.sum() / d * held:>8.1%}")
pl = ok[ok["product"] == "personal"]
print("\npersonal loans by Mark II-R band, IRB")
print(f"{'band':<10}{'loans':>7}{'PD':>7}{'weight':>8}{'CET1':>7}")
order = ["<560", "560-579", "580-599", "600-619", "620+"]
bands = dict(list(pl.groupby("band")))
for b in order:
    g = bands[b]
    d = g.drawn_cents.sum()
    rw = g.irb_rwa.sum() / d
    pdw = (g.pd_floored * g.drawn_cents).sum() / d
    print(f"{b:<10}{len(g):>7,}{pdw:>7.2%}{rw:>8.0%}{rw * held:>7.1%}")
print("weight: IRB RWA over balance; CET1: that times the ratio held")
