# Exercise 27.2: returns charged on economic capital only, and on
# regulatory capital only, beside the larger of the two.
import fernhill
from ballast import appetite as ap

con = fernhill.connect()
t = ap.returns(con)
mk = ap.market(con)
print(f"{'segment':<14}{'larger':>8}{'EC only':>9}{'reg only':>10}")
for name, r in t.iterrows():
    base = r.income - r.funding - r.el
    ec = (base + r.ec * mk["cof"] / 100) / r.ec
    reg = (base + r.reg * mk["cof"] / 100) / r.reg
    big = f"{ec:>9.0%}" if abs(ec) < 10 else f"{'>999%':>9}"
    print(f"{name:<14}{r.roc:>8.0%}{big}{reg:>10.0%}")
