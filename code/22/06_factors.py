# The economy each year's defaults imply, segment by segment; how much
# of it the segments share; and what companies' share prices add.
import fernhill
from ballast import portfolio as pf

con = fernhill.connect()
h = pf.default_history(con)
est = pf.load_json("correlations.json")
f = pf.factor_history(h, est)
short = ["pers", "card", "auto", "mortg", "term", "o/d", "cos"]
print("The economy each year's defaults imply (negative is bad)")
print(f"{'year':<6}" + "".join(f"{s:>7}" for s in short))
for y, row in f.iterrows():
    print(f"{y:<6}" + "".join(f"{v:>7.2f}" for v in row))
fac = pf.shared(con, est, h)
print(f"{'shared':<6}" + "".join(f"{fac['beta'][s]:>7.2f}"
                                 for s in f.columns))

print(f"\nlisted clients: {fac['companies']}; correlation of monthly "
      "asset returns")
print(f"  same sector   {fac['within']:.3f} "
      f"({fac['pairs_within']:,} pairs)")
print(f"  other sectors {fac['across']:.3f} "
      f"({fac['pairs_across']:,} pairs)")
print(f"share of a sector's factor common to all companies: "
      f"{fac['common']:.2f}")
print("saved:", pf.save_json(fac, "factors.json"))
