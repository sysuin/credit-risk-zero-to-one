# Fernhill's provision on 31 December 2025 by product and stage,
# with the coverage of each, and a check against Chapter 18's PD.
# timeout: 300
import json
from pathlib import Path

import fernhill
from ballast import ecl

con = fernhill.connect()
r = ecl.run(con, ecl.AS_OF)
order = list(ecl.RETAIL) + ["commercial_term", "commercial_revolver"]
t = r.pivot_table(index="product", columns="stage", values="ecl",
                  aggfunc="sum", fill_value=0).reindex(order) / 1e8
bal = r.groupby("product")["balance_cents"].sum().reindex(order)

print(f"{'$m':<19}{'balance':>8}{'stage 1':>8}{'stage 2':>8}"
      f"{'stage 3':>8}{'total':>8}{'cover':>7}")
for p in order:
    s = t.loc[p]
    print(f"{p:<19}{bal[p] / 1e8:>8,.0f}{s.get(1, 0):>8.2f}"
          f"{s.get(2, 0):>8.2f}{s.get(3, 0):>8.2f}{s.sum():>8.2f}"
          f"{s.sum() * 1e8 / bal[p]:>7.2%}")
tot = t.sum()
print("-" * 66)
print(f"{'all':<19}{bal.sum() / 1e8:>8,.0f}{tot.get(1, 0):>8.2f}"
      f"{tot.get(2, 0):>8.2f}{tot.get(3, 0):>8.2f}{tot.sum():>8.2f}"
      f"{tot.sum() * 1e8 / bal.sum():>7.2%}")

pl = r[(r["product"] == "personal") & (r["stage"] < 3)
       & (r["mob"] >= 1) & (r["missed"] <= 2)]
print(f"\npersonal loans performing, a month old or more: "
      f"{len(pl):,}; 12-month PD")
print(f"weighted {pl['pd12'].mean():.2%}, base "
      f"{pl['pd12_base'].mean():.2%} "
      "(Chapter 18's model: 2.97%, 2.50%)")
Path(__file__).with_suffix(".json").write_text(json.dumps(
    {p: {str(k): float(v) for k, v in t.loc[p].items()}
     for p in order}) + "\n")
