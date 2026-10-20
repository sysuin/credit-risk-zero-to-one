# timeout: 600
# Exercise 22.4: sell half of Fernhill's largest exposure, Falcon Vale
# Holdings, and see what it releases.
import fernhill
from ballast import capital, portfolio as pf

con = fernhill.connect()
est = pf.load_json("correlations.json")
fac = pf.load_json("factors.json")
pools, names = pf.book(con, capital.load())
model = pf.model_from(est, fac)
big = names.ead.idxmax()
sold = names.ead[big] / 2
before = pf.simulate(pools, names, model)
after_names = names.copy()
after_names.loc[big, "ead"] = sold
after = pf.simulate(pools, after_names, model)
m = 1e8
print(f"sold ${sold / m:,.1f}m of {names.company_id[big]}")
print(f"{'':<6}{'before':>9}{'after':>9}{'change':>9}  ($m)")
for k, f in [("EL", "el"), ("VaR", "var"), ("ES", "es"),
             ("EC", "ec")]:
    b, a = getattr(before, f)(), getattr(after, f)()
    print(f"{k:<6}{b / m:>9.1f}{a / m:>9.1f}{(a - b) / m:>+9.1f}")
book = names.ead.sum() + pools.ead.sum()
print(f"EC released per dollar sold: "
      f"{(before.ec() - after.ec()) / sold:.1%}; book average "
      f"{before.ec() / book:.1%}")
