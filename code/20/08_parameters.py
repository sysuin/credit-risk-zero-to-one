# The parameters the engine adds to Chapters 18 and 19: LGD at the
# contract rate, prepayment, and the uplift for arrears and use of
# the limit.
# timeout: 300
import fernhill
from ballast import ecl
from ballast.parameters import lgd as lgdm

con = fernhill.connect()
params = ecl.parameters(con)
ch19 = lgdm.load()["products"]
t = params["lgd"]
print(f"{'LGD':<22}{'workouts':>9}{'Ch 19':>8}{'contract':>10}"
      f"{'downturn':>10}{'prepaid':>9}")
print(f"{'':<22}{'':>9}{'funding':>8}{'rate':>10}{'':>10}"
      f"{'a month':>9}")
for p, row in t.iterrows():
    old = f"{ch19[p]['lgd']:>8.1%}" if p in ch19 else f"{'-':>8}"
    pre = params["prepay"].get(p)
    pre = f"{pre:>9.2%}" if pre is not None else f"{'-':>9}"
    print(f"{p:<22}{int(row['workouts']):>9,}{old}{row['lgd']:>10.1%}"
          f"{row['downturn']:>10.1%}{pre}")

u = params["uplift"]
cols = ("personal", "card", "mortgage")
print("\n12-month default rate by pool, quarter ends to December")
print("2024, and its uplift on the product's rate")
print(f"{'pool':<9}" + "".join(f"{p:>17}" for p in cols))
for q in ("u<50", "clean", "u50-90", "u90+", "recent", "30", "60"):
    cells = ""
    for p in cols:
        if (p, q) in u.index:
            g = u.loc[(p, q)]
            cells += f"{g['rate']:>10.1%} x{g['uplift']:>5.1f}"
        else:
            cells += f"{'':>17}"
    print(f"{q:<9}{cells}".rstrip())
