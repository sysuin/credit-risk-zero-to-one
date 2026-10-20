# timeout: 600
# Ballast's portfolio run for 31 December 2025, from the loan book:
# estimate, simulate, save the loss distribution, and read it back.
import fernhill
from ballast import portfolio as pf

con = fernhill.connect()
run = pf.run(con)
summary, rows = pf.summarise(run)
for path in pf.save(summary, rows):
    print("saved:", path)

s = pf.load()
m = 1e8
print(f"{s['years']:,} years, seed {s['seed']}; "
      f"{s['exposures']['accounts']:,} accounts in "
      f"{s['exposures']['pools']} pools, "
      f"{s['exposures']['companies']} companies")
print(f"EL ${s['el'] / m:,.1f}m (formula ${s['el_formula'] / m:,.1f}m)"
      f", VaR 99.9% ${s['quantiles']['0.999'] / m:,.1f}m, "
      f"ES ${s['es']['0.999'] / m:,.1f}m")
print(f"economic capital ${s['ec_999'] / m:,.1f}m")
c = pf.load_contributions()
print(f"contributions: {len(c)} rows, summing to "
      f"${c.es_999.sum() / m:,.1f}m of ES")
