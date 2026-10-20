# The month-end run: the provision of 31 December 2024 carried to 31
# December 2025, account by account, as stage moves and a waterfall.
# timeout: 600
import datetime as dt
import json
from pathlib import Path

import fernhill
import pandas as pd
from ballast import ecl

con = fernhill.connect()
OPEN = dt.date(2024, 12, 31)
p0, p1 = ecl.parameters(con, OPEN), ecl.parameters(con)
r0, r1 = ecl.run(con, OPEN, p0), ecl.run(con, ecl.AS_OF, p1)

a = r0.set_index("account_id")["stage"]
b = r1.set_index("account_id")["stage"]
moves = pd.crosstab(a, b.reindex(a.index).fillna(0).astype(int))
moves = moves.rename(columns={0: "left"})
print("accounts by stage, December 2024 (rows) to December 2025")
print(f"{'':<8}" + "".join(f"{str(c):>8}" for c in moves.columns))
for s, row in moves.iterrows():
    print(f"{s:<8}" + "".join(f"{v:>8,}" for v in row))
print(f"{'new':<8}" + "".join(
    f"{(b.drop(a.index, errors='ignore') == c).sum():>8,}"
    if c != "left" else f"{'':>8}" for c in moves.columns))

m = ecl.movement(con, r0, r1, p0, p1)
print(f"\n{'provision, $m':<24}{'retail':>10}{'commercial':>12}"
      f"{'all':>10}")
for k, v in m.iterrows():
    print(f"{k:<24}{v['retail'] / 1e8:>10.2f}"
          f"{v['commercial'] / 1e8:>12.2f}{v['all'] / 1e8:>10.2f}")
check = m["all"].drop("closing").sum() - m.loc["closing", "all"]
print(f"the steps add up to the closing provision: {abs(check) < 1}")
Path(__file__).with_suffix(".json").write_text(json.dumps(
    {k: float(v) / 1e8 for k, v in m["all"].items()}) + "\n")
c0 = r0[r0["segment"] == "commercial"].set_index("account_id")
c1 = r1[r1["segment"] == "commercial"].set_index("account_id")
k = c0.index.intersection(c1.index)
moved = (c1.loc[k, "grade"] - c0.loc[k, "grade"]).astype(int)
print(f"commercial facilities in both: {len(k)}; months to maturity "
      f"{c0.loc[k, 'remaining'].mean():.0f} -> "
      f"{c1.loc[k, 'remaining'].mean():.0f}")
print(f"  regraded worse {(moved > 0).sum()}, better "
      f"{(moved < 0).sum()}, same {(moved == 0).sum()}")
