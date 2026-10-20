# Exercise 21.3: Chapter 12's capital charge per personal-loan band,
# with flat capital at 10% of the balance against IRB capital at the
# CET1 ratio Fernhill holds (hurdle 15%, transfer price 3.33%).
import fernhill
from ballast import capital

HURDLE, FTP, FLAT = 0.15, 0.0333, 0.10
con = fernhill.connect()
r = capital.load()
k = capital.bank_capital(con)
held = k["cet1"] / (r.sa_rwa.sum() + k["operational_rwa"]
                    + k["market_rwa"])
pl = r[(r["product"] == "personal") & ~r.in_default
       & (r.drawn_cents > 0)]
print(f"{'band':<10}{'capital':>9}{'charge':>8}{'flat charge':>13}")
for b in ["<560", "560-579", "580-599", "600-619", "620+"]:
    g = pl[pl.band == b]
    cap = g.irb_rwa.sum() / g.drawn_cents.sum() * held
    print(f"{b:<10}{cap:>9.1%}{cap * (HURDLE - FTP):>8.2%}"
          f"{FLAT * (HURDLE - FTP):>13.2%}")
print("charge: capital x (hurdle - transfer price), a year, of balance")
