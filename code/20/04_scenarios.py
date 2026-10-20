# The provision under each of the four scenarios published for 31
# December 2025, weighted, and at the scenarios' average path.
# timeout: 300
import json
from pathlib import Path

import fernhill
from ballast import ecl

con = fernhill.connect()
params = ecl.parameters(con)
sc = params["scenarios"]
r = ecl.run(con, ecl.AS_OF, params)
w = sc["weight"]

print(f"{'scenario':<10}{'weight':>7}{'2026':>7}{'peak':>7}{'2030':>7}"
      f"{'retail':>9}{'commercial':>12}{'all':>9}")
print(f"{'':<10}{'':>7}{'unemployment, %':>21}{'provision, $m':>30}")
total = {}
for s, row in sc.iterrows():
    u = row["path"]
    seg = r.groupby("segment")[f"ecl_{s}"].sum() / 1e8
    total[s] = seg.sum()
    print(f"{s:<10}{w[s]:>7.0%}{u[:12].mean():>7.2f}{u.max():>7.2f}"
          f"{u[-1]:>7.2f}{seg['retail']:>9.1f}"
          f"{seg['commercial']:>12.1f}{total[s]:>9.1f}")
seg = r.groupby("segment")["ecl"].sum() / 1e8
print(f"{'weighted':<38}{seg['retail']:>9.1f}{seg['commercial']:>12.1f}"
      f"{seg.sum():>9.1f}")

# The same weights on one path, the scenarios' weighted average.
mean = sum(w[s] * sc.loc[s, "path"] for s in sc.index)
flat = sc.copy()
flat["path"] = [mean] * len(sc)
m = ecl.run(con, ecl.AS_OF, dict(params, scenarios=flat),
            stages=r.set_index("account_id")["stage"])
seg = m.groupby("segment")["ecl"].sum() / 1e8
print(f"{'at the average path':<38}{seg['retail']:>9.1f}"
      f"{seg['commercial']:>12.1f}{seg.sum():>9.1f}")
up = r["ecl"].sum() / 1e8 / total["base"] - 1
print(f"\nweighted over base: {up:+.1%}; over the average path: "
      f"{r['ecl'].sum() / m['ecl'].sum() - 1:+.1%}")
base_only = ecl.stage(r.assign(pd12=r["pd12_base"]))["stage"]
print(f"stage 2 on the weighted PD: {(r['stage'] == 2).sum():,} "
      f"accounts; on the base PD: {(base_only == 2).sum():,}")
Path(__file__).with_suffix(".json").write_text(json.dumps(
    {"scenarios": total, "weights": {k: float(v) for k, v in w.items()},
     "weighted": float(r["ecl"].sum() / 1e8),
     "average_path": float(m["ecl"].sum() / 1e8)}) + "\n")
