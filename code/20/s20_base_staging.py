# Exercise 2: how much of the weighted provision's lead over the base
# comes from staging on the weighted PD rather than the base PD.
# timeout: 300
import fernhill
from ballast import ecl

con = fernhill.connect()
params = ecl.parameters(con)
r = ecl.run(con, ecl.AS_OF, params)
base_stage = ecl.stage(r.assign(pd12=r["pd12_base"]))["stage"]
b = ecl.run(con, ecl.AS_OF, params,
            stages=base_stage.set_axis(r["account_id"]))
print(f"{'staged on':<14}{'stage 2':>9}{'base only':>11}"
      f"{'weighted':>10}")
for name, x in (("weighted PD", r), ("base PD", b)):
    print(f"{name:<14}{(x['stage'] == 2).sum():>9,}"
          f"{x['ecl_base'].sum() / 1e8:>10.1f}m"
          f"{x['ecl'].sum() / 1e8:>9.1f}m")
