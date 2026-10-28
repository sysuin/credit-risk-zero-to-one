# Fernhill's capital ratios on 31 December 2025 under three choices,
# against the minimums plus buffers, and its leverage ratio.
import json

import fernhill
from ballast import capital

con = fernhill.connect()
r = capital.load()
k = capital.bank_capital(con)
prov = capital.provisions().set_index("account_id")["ecl"]
r["prov"] = r.account_id.map(prov).fillna(0)
other = k["operational_rwa"] + k["market_rwa"]
sa = capital.credit_rwa(r) + other
req = capital.requirements()
minimums = [f"{n} {v:.1%}" for n, v in capital.MINIMUM.items()]
print("minimums: " + ", ".join(minimums))
print("required, with conservation and an illustrative "
      f"{capital.COUNTERCYCLICAL:.0%}\ncountercyclical buffer:")
required = [f"{n} {v:.1%}" for n, v in req.items()]
print("  " + ", ".join(required))
print(f"\n{'':<20}{'RWA $m':>8}{'CET1':>7}{'Tier 1':>8}{'total':>7}"
      f"{'CET1 spare $m':>15}")
choices = {"standardised": [],
           "mortgages on IRB": ["mortgage"],
           "everything on IRB": list(r["product"].unique())}
out = {}
for name, prods in choices.items():
    # Products on IRB, their provisions less expected loss, the ratios.
    on = r["product"].isin(prods)
    credit = capital.credit_rwa(r, prods)
    total = capital.output_floor(credit + other, sa)
    gap = (r.prov - r.el)[on].sum()
    x = capital.ratios(k, total, gap, r.irb_rwa[on].sum())
    spare = (x["cet1"] - req["cet1"]) * total
    out[name] = {"rwa": total}
    out[name].update(x)
    print(f"{name:<20}{total / 1e8:>8,.0f}{x['cet1']:>7.1%}"
          f"{x['tier1']:>8.1%}{x['total']:>7.1%}{spare / 1e8:>15,.0f}")
tier1 = k["cet1"] + k["at1"]
lev = capital.leverage_exposure(r)
print(f"\nleverage: Tier 1 ${tier1 / 1e8:,.0f}m over loan-book "
      f"exposure ${lev / 1e8:,.0f}m\n= {tier1 / lev:.1%} (minimum "
      f"{capital.LEVERAGE_MIN:.0%})")
print(f"loan book needed for 3% at today's Tier 1: "
      f"${tier1 / capital.LEVERAGE_MIN / 1e8:,.0f}m")
with open("code/21/17_ratios.json", "w") as f:
    json.dump({"capital": k, "req": req, "sa_rwa": sa,
               "min": capital.MINIMUM, "out": out}, f)
