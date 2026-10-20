# The provision at each year end of the stress, the accounts that
# move to stage 2, and the charge each year: losses plus the change.
import json

import fernhill
from ballast import ecl, stress

con = fernhill.connect()
s = stress.load()
y0 = s["summary"]["year_zero"]
e = ecl.load()
bal = e.balance_cents.sum()
st2 = (e.stage == 2).sum()
print(f"31 Dec 2025: provision ${y0['provision'] / 1e8:,.2f}m, "
      f"{st2:,} accounts in stage 2,")
print(f"{(e.balance_cents[e.stage == 2].sum() / bal):.1%} of the "
      f"balance; coverage {y0['provision'] / bal:.2%}")
print(f"\n{'year':<5}{'provision':>10}{'cover':>7}{'stage 2':>8}"
      f"{'of bal':>8}{'losses':>8}{'change':>8}{'charge':>8}")
for k, g in s["years"].groupby("scenario", sort=False):
    print(k)
    prev = y0["provision"]
    for r in g.itertuples():
        print(f"{r.year:<5}{r.provision / 1e8:>10.1f}"
              f"{r.provision / bal:>7.2%}{r.stage2:>8,}"
              f"{r.stage2_bal / bal:>8.1%}{r.loss / 1e8:>8.1f}"
              f"{(r.provision - prev) / 1e8:>+8.1f}"
              f"{r.charge / 1e8:>8.1f}")
        prev = r.provision
p = s["products"]
p = p[p.scenario == "stress_2026"].pivot(index="product",
                                         columns="year",
                                         values="provision") / 1e8
c = p.loc[["commercial_term", "commercial_revolver"]].sum()
print("\nstress_2026, the commercial book's share of the provision:")
share = [f"{y} {c[y] / p[y].sum():.0%}" for y in p.columns]
print("  " + ", ".join(share))
out = {"y0": y0["provision"] / 1e8, "years": {
    k: {"loss": list(g.loss / 1e8),
        "provision": list(g.provision / 1e8)}
    for k, g in s["years"].groupby("scenario", sort=False)}}
with open("code/26/07_provisions.json", "w") as f:
    json.dump(out, f)
