# Satellite models: each product's yearly default rate on the year's
# unemployment, with honest standard errors, against Chapter 18.
import json

import fernhill
from ballast import stress
from ballast.parameters import pd as pdm

con = fernhill.connect()
h = stress.default_history(con)
hz = pdm.load_hazards()
yr = stress.annual(stress.paths(con)["stress_2026"]).loc[2027]
prods = ["personal", "card", "auto", "mortgage", "sme_term",
         "sme_overdraft", "commercial"]
print("logit(default rate) = a + b x unemployment, 2017-2025, nine")
print("years; se scaled for overdispersion; Ch18 = hazard's b")
print(f"{'':<14}{'b':>6}{'(se)':>7}{'no 2020':>8}{'Ch18':>6}"
      f"{'2027 stress, 90%':>21}")
fits = {}
for p in prods:
    f = stress.fit_satellite(h, p)
    g = stress.fit_satellite(h, p, drop_years=[2020])
    rate, lo, hi = stress.satellite_rate(f, {"u": yr.u})
    ch18 = (f"{hz[p].default['u']:>6.3f}" if p in hz
            else f"{'-':>6}")
    print(f"{p:<14}{f['params']['u']:>6.3f}{f['bse']['u']:>7.3f}"
          f"{g['params']['u']:>8.3f}{ch18}"
          f"{rate:>7.1%} ({lo:.1%}-{hi:.1%})")
    fits[p] = {"fit": f, "no2020": g, "rate": rate, "lo": lo,
               "hi": hi}
print(f"(stress 2027: unemployment {yr.u:.2f}%, policy rate "
      f"{yr.policy:.2f}%)")

print("\nA second driver, added to unemployment: its b (se)")
print(f"{'':<14}{'policy rate':>15}{'price index change':>22}")
price = {"mortgage": "hpi_chg", "auto": "car_chg"}
for p in prods:
    f = stress.fit_satellite(h, p, ("u", "policy"))
    cell = f"{f['params']['policy']:>7.3f} ({f['bse']['policy']:.3f})"
    extra = ""
    if p in price:
        g = stress.fit_satellite(h, p, ("u", price[p]))
        k = price[p]
        name = "houses" if p == "mortgage" else "cars"
        extra = f"{name:>9} {g['params'][k]:>6.2f} ({g['bse'][k]:.2f})"
    print(f"{p:<14}{cell:>15}{extra:>22}".rstrip())

c = stress.fit_satellite(h, "commercial", ("u", "policy"))
rate, lo, hi = stress.satellite_rate(c, {"u": yr.u,
                                         "policy": yr.policy})
print("\ncommercial on both: b(unemployment) "
      f"{c['params']['u']:.3f} ({c['bse']['u']:.3f}),")
print(f"  b(rate) {c['params']['policy']:.3f} "
      f"({c['bse']['policy']:.3f})")
print(f"  2027 stress: {rate:.1%} (90%: {lo:.1%} to {hi:.1%})")
fits["commercial_both"] = {"fit": c, "rate": rate, "lo": lo, "hi": hi}
with open("code/26/03_satellite.json", "w") as f:
    json.dump({"fits": fits, "stress_u": yr.u,
               "history": h.to_dict("records")}, f)
