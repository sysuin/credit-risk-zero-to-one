# Exercise 21.2: the mortgage LGD at which the IRB approach needs as
# much capital as the standardised one.
from ballast import capital

r = capital.load()
m = r[r["product"] == "mortgage"].copy()
sa = m.sa_rwa.sum()
lo, hi = 0.10, 1.0
for _ in range(50):
    mid = (lo + hi) / 2
    if capital.irb(m, mortgage_floor=mid).irb_rwa.sum() < sa:
        lo = mid
    else:
        hi = mid
print(f"standardised mortgage RWA ${sa / 1e8:,.1f}m")
print(f"IRB matches it at an LGD of {lo:.1%}")
for f in (0.10, 0.20, 0.30):
    x = capital.irb(m, mortgage_floor=f).irb_rwa.sum()
    print(f"  LGD {f:.0%}: IRB ${x / 1e8:,.1f}m")
