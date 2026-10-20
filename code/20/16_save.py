# Ballast's provision on 31 December 2025, one row per account, saved
# for the capital, stress and reporting chapters, and read back.
# timeout: 300
import fernhill
from ballast import ecl

con = fernhill.connect()
params = ecl.parameters(con)
r = ecl.run(con, ecl.AS_OF, params)
r["cecl"] = ecl.run(con, ecl.AS_OF, params, basis="cecl")["ecl"]
path = ecl.save(r)
back = ecl.load()
print(f"saved {path}")
print(f"read back: {len(back):,} accounts, {back.shape[1]} columns")
t = ecl.summary(back, by=("segment", "stage"))
print(f"\n{'segment':<12}{'stage':>6}{'accounts':>10}{'balance':>12}"
      f"{'provision':>12}{'cover':>8}")
for (seg, st), v in t.iterrows():
    print(f"{seg:<12}{st:>6}{int(v.accounts):>10,}"
          f"{v.balance_cents / 1e8:>11,.0f}m{v.ecl_cents / 1e8:>11.2f}m"
          f"{v.coverage:>8.2%}")
print(f"{'all':<18}{len(back):>10,}"
      f"{back['balance_cents'].sum() / 1e8:>11,.0f}m"
      f"{back['ecl'].sum() / 1e8:>11.2f}m"
      f"{back['ecl'].sum() / back['balance_cents'].sum():>8.2%}")
print(f"CECL alongside: ${back['cecl'].sum() / 1e8:,.2f}m")
