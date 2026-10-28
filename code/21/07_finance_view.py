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
sa = capital.standardised(capital.book(con), capital.provisions())

# The spreadsheet: a flat weight on what is drawn, plus 40% of every
# company's unused limit, term loans included.
sa["flat"] = sa.drawn_cents * sa["product"].map(FLAT)
unused = (sa.limit_cents - sa.drawn_cents).clip(lower=0)
com = sa.segment == "commercial"
sa.loc[com, "flat"] += HEADROOM * unused[com]

g = sa.groupby("product")[["flat", "sa_rwa"]].sum() / 1e8
print(f"{'$m':<20}{'flat':>8}{'Ballast':>9}{'gap':>8}")
for product, row in g.iterrows():
    print(f"{product:<20}{row.flat:>8,.1f}{row.sa_rwa:>9,.1f}"
          f"{row.flat - row.sa_rwa:>8,.1f}")
t = g.sum()
print(f"{'credit RWA':<20}{t.flat:>8,.1f}{t.sa_rwa:>9,.1f}"
      f"{t.flat - t.sa_rwa:>8,.1f}")

# The part of the flat figure that is repaid term-loan principal.
term = sa["product"] == "commercial_term"
lent = HEADROOM * (sa.limit_cents - sa.drawn_cents)[term].sum()
print(f"\nrepaid term-loan principal counted as a commitment: "
      f"${lent / 1e8:,.1f}m")

# The CET1 ratio each way, with the same operational and market RWA.
k = capital.bank_capital(con)
other = k["operational_rwa"] + k["market_rwa"]
for name, credit in (("flat weights", t.flat * 1e8),
                     ("Ballast, standardised", t.sa_rwa * 1e8)):
    total = credit + other
    print(f"{name:<22} total RWA ${total / 1e8:,.0f}m, CET1 "
          f"{k['cet1'] / total:.1%}")
