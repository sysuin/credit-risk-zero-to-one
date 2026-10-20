# The auditor's question: what the provision would be if the downside
# scenario carried 20% or 40% instead of 30%, the base taking up the
# difference.
# timeout: 300
import fernhill
from ballast import ecl

con = fernhill.connect()
params = ecl.parameters(con)
rows = []
for down in (0.20, 0.30, 0.40):
    sc = params["scenarios"].copy()
    sc.loc["downside", "weight"] = down
    sc.loc["base", "weight"] = 0.70 - down
    r = ecl.run(con, ecl.AS_OF, dict(params, scenarios=sc))
    rows.append((down, r["ecl"].sum() / 1e8, (r["stage"] == 2).sum()))
ref = rows[1][1]
print(f"{'downside':>9}{'base':>7}{'provision':>11}{'change':>9}"
      f"{'stage 2':>9}")
for down, total, two in rows:
    print(f"{down:>9.0%}{0.70 - down:>7.0%}{total:>10.1f}m"
          f"{total - ref:>+8.1f}m{two:>9,}")
