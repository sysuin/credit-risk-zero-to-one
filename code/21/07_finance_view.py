# The finance team's capital ratio, from flat weights by product,
# against Ballast's standardised RWA, product by product.
import fernhill
from ballast import capital

con = fernhill.connect()
FLAT = {"mortgage": 0.35, "personal": 0.75, "card": 0.75,
        "auto": 0.75, "sme_term": 0.85, "sme_overdraft": 0.85,
        "sme_emergency": 0.20, "commercial_term": 1.00,
        "commercial_revolver": 1.00}
HEADROOM = 0.40          # every unused facility limit, term or not
s = capital.standardised(capital.book(con), capital.provisions())
s["flat"] = s.drawn_cents * s["product"].map(FLAT)
com = s.segment == "commercial"
s.loc[com, "flat"] += HEADROOM * (s.limit_cents - s.drawn_cents
                                  ).clip(lower=0)[com]
g = s.groupby("product")[["flat", "sa_rwa"]].sum() / 1e8
print(f"{'$m':<20}{'flat':>8}{'Ballast':>9}{'gap':>8}")
for p, r in g.iterrows():
    print(f"{p:<20}{r.flat:>8,.1f}{r.sa_rwa:>9,.1f}"
          f"{r.flat - r.sa_rwa:>8,.1f}")
t = g.sum()
print(f"{'credit RWA':<20}{t.flat:>8,.1f}{t.sa_rwa:>9,.1f}"
      f"{t.flat - t.sa_rwa:>8,.1f}")
term = s["product"] == "commercial_term"
lent = HEADROOM * (s.limit_cents - s.drawn_cents)[term].sum()
print(f"\nrepaid term-loan principal counted as a commitment: "
      f"${lent / 1e8:,.1f}m")
k = capital.bank_capital(con)
other = k["operational_rwa"] + k["market_rwa"]
for name, credit in (("flat weights", t.flat * 1e8),
                     ("Ballast, standardised", t.sa_rwa * 1e8)):
    total = credit + other
    print(f"{name:<22} total RWA ${total / 1e8:,.0f}m, CET1 "
          f"{k['cet1'] / total:.1%}")
