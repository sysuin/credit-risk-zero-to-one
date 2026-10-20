# Fernhill's book on 31 December 2025, staged by Ballast's rule:
# accounts and balances in each stage, and why stage 2 is stage 2.
# timeout: 300
import json
from pathlib import Path

import fernhill
from ballast import ecl

con = fernhill.connect()
r = ecl.run(con, ecl.AS_OF)

print(f"{'product':<19}{'accounts':>9}{'balance':>9}{'stage 1':>8}"
      f"{'stage 2':>8}{'stage 3':>8}{'in 2+3':>7}")
order = list(ecl.RETAIL) + ["commercial_term", "commercial_revolver"]
for p in order + ["all"]:
    g = r if p == "all" else r[r["product"] == p]
    n = g["stage"].value_counts()
    bal = g["balance_cents"].sum()
    hit = g.loc[g["stage"] > 1, "balance_cents"].sum() / bal
    if p == "all":
        print("-" * 68)
    print(f"{p:<19}{len(g):>9,}{bal / 1e8:>8,.0f}m"
          f"{n.get(1, 0):>8,}{n.get(2, 0):>8,}{n.get(3, 0):>8,}"
          f"{hit:>7.1%}")
why = r.loc[r["stage"] == 2, "reason"].value_counts()
print("\nstage 2, by the first rule that applies:")
print("  " + "   ".join(f"{k} {v:,}" for k, v in why.items()))
out = {"reasons": {k: int(v) for k, v in why.items()},
       "stages": {str(k): int(v) for k, v in
                  r["stage"].value_counts().sort_index().items()},
       "accounts": int(len(r))}
Path(__file__).with_suffix(".json").write_text(json.dumps(out) + "\n")
