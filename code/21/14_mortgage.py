# The supervisor's question: the mortgage book's RWA on the IRB
# approach against the standardised, by loan-to-value, and how much
# the answer depends on the LGD floor and the scaling factor.
import fernhill
import pandas as pd
from ballast import capital

con = fernhill.connect()
r = capital.load()
m = r[r["product"] == "mortgage"].copy()
# Band edges 0, 50%, 60%, 80%, 90%, then anything above.
m["ltv_band"] = pd.cut(m.ltv, [0] + capital.LTV_EDGES[:4] + [9],
                       labels=["up to 50%", "50-60%", "60-80%",
                               "80-90%", "over 90%"])
g = m.groupby("ltv_band", observed=True).agg(
    n=("account_id", "size"), sa=("sa_rwa", "sum"),
    irb=("irb_rwa", "sum"), ead=("irb_ead", "sum"))
print(f"{'loan-to-value':<14}{'loans':>6}{'SA RWA':>8}{'IRB RWA':>9}"
      f"{'SA wt':>7}{'IRB wt':>8}")
for k, x in g.iterrows():
    print(f"{k:<14}{int(x.n):>6,}{x.sa / 1e8:>8,.1f}"
          f"{x.irb / 1e8:>9,.1f}{x.sa / x.ead:>7.0%}"
          f"{x.irb / x.ead:>8.1%}")
sa, ir = m.sa_rwa.sum(), m.irb_rwa.sum()
print(f"{'all':<14}{len(m):>6,}{sa / 1e8:>8,.1f}{ir / 1e8:>9,.1f}"
      f"{sa / m.sa_ead.sum():>7.0%}{ir / m.irb_ead.sum():>8.1%}")
perf = m[~m.in_default]
pdw = (perf.pd_floored * perf.irb_ead).sum() / perf.irb_ead.sum()
print(f"$m; performing PD (EAD-weighted) {pdw:.2%}"
      f";\nin default: {m.in_default.sum()} loans, IRB RWA "
      f"${m[m.in_default].irb_rwa.sum() / 100:,.0f}")

print("\nIRB RWA $m under other choices")
cases = {"supervisor's floor, 10% LGD": capital.irb(m),
         "Basel floor only, 5% LGD": capital.irb(m, mortgage_floor=0.0),
         "a 15% LGD floor": capital.irb(m, mortgage_floor=0.15),
         "10% LGD, scaled by 1.06": capital.irb(m, scaling=1.06)}
for name, run in cases.items():
    x = run.irb_rwa.sum()
    print(f"  {name:<30}{x / 1e8:>7,.1f}{x / sa:>7.0%} of SA")

# The CET1 the saving frees: at the requirement, and at the ratio held.
k = capital.bank_capital(con)
total_sa = r.sa_rwa.sum() + k["operational_rwa"] + k["market_rwa"]
held = k["cet1"] / total_sa
need = capital.requirements()["cet1"]
saved = sa - ir
print(f"\nRWA saved ${saved / 1e8:,.1f}m; CET1 it frees at "
      f"{need:.1%}: ${saved * need / 1e8:,.1f}m; at the {held:.1%}")
print(f"Fernhill holds: ${saved * held / 1e8:,.1f}m; at a 15% "
      f"hurdle, ${saved * need * 0.15 / 1e8:,.1f}m to "
      f"${saved * held * 0.15 / 1e8:,.1f}m a year")
