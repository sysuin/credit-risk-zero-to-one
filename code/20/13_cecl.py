# Fernhill's book under CECL beside IFRS 9, by product: lifetime losses
# from the first day, with the forecast reverting after two years.
# timeout: 300
import fernhill
from ballast import ecl

con = fernhill.connect()
params = ecl.parameters(con)
i9 = ecl.run(con, ecl.AS_OF, params)
ce = ecl.run(con, ecl.AS_OF, params, basis="cecl")
order = list(ecl.RETAIL) + ["commercial_term", "commercial_revolver"]
a = i9.groupby("product")["ecl"].sum().reindex(order) / 1e8
b = ce.groupby("product")["ecl"].sum().reindex(order) / 1e8
s1 = i9.assign(add=ce["ecl"] - i9["ecl"])
s1 = s1[s1["stage"] == 1].groupby("product")["add"].sum() / 1e8
print(f"{'':<20}{'':>9}{'':>9}{'':>7}{'difference from':>20}")
print(f"{'$m':<20}{'IFRS 9':>9}{'CECL':>9}{'ratio':>7}{'stage 1':>9}"
      f"{'stages 2-3':>11}")
for p in order + ["all"]:
    x, y, z = ((a.sum(), b.sum(), s1.sum()) if p == "all"
               else (a[p], b[p], s1[p]))
    if p == "all":
        print("-" * 65)
    print(f"{p:<20}{x:>9.2f}{y:>9.2f}{y / x:>7.2f}{z:>9.2f}"
          f"{round(y - x - z, 2) + 0.0:>11.2f}")
print(f"\ncards under CECL: balances run off at "
      f"{params['card_paydown']:.1%} a month, no limit")
flat = ecl.run(con, ecl.AS_OF, dict(params, card_paydown=0.0),
               basis="cecl")
c = flat.loc[flat["product"] == "card", "ecl"].sum() / 1e8
print(f"if today's card balances did not run off: ${c:.2f}m")
