# The watchlist: three early-warning triggers beside the grade, what
# they add, what they cost in reviews, and a threshold traded off.
import json

import pandas as pd

import fernhill
from ballast import monitoring as mon
from ballast.config import ROOT

con = fernhill.connect()
p = mon.business_panel(con)
w = mon.watch(p)
early = w[list(mon.WATCHLIST)].any(axis=1)
lists = pd.DataFrame({"grade 8 or worse": w["grade_8"],
                      "early warning": early,
                      "either": w["grade_8"] | early})
r = mon.watch_record(p, lists)
known = p["default_12m"].notna()
months = p.loc[known, "month"].nunique()
print(f"early warning = {' or '.join(mon.WATCHLIST)}")
print(f"{'list':<18}{'hit rate':>9}{'caught':>10}{'false':>7}"
      f"{'on list':>9}")
print(f"{'':<18}{'':>9}{'':>10}{'alarms':>7}{'a month':>9}")
for x in r.itertuples():
    print(f"{x.flag:<18}{x.hit_rate:>9.1%}{x.caught:>5} of {x.defaults}"
          f"{x.false_alarms:>7}{x.months / months:>9.1f}")
good = p["grade"] <= 7
sub = mon.watch_record(p[good], lists[good][["early warning"]])
s = sub.iloc[0]
base = p.loc[good & known, "default_12m"].mean()
print(f"\nclients graded 7 or better: {base:.2%} of months followed by")
print(f"a default; early warning hit {s.hit_rate:.1%} and caught "
      f"{s.caught} of {s.defaults}")
print(f"defaults, with {s.false_alarms} false alarms")

print("\nrevolver use threshold, alone")
print(f"{'drawn':<8}{'months':>8}{'hit rate':>10}{'caught':>8}")
sweep = []
for k in (0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
    f = pd.DataFrame({"x": p["revolver_use"] >= k})
    x = mon.watch_record(p, f).iloc[0]
    sweep.append({"k": k, "hit": round(x.hit_rate, 4),
                  "caught": int(x.caught)})
    print(f"{k:<8.0%}{x.months:>8,}{x.hit_rate:>10.1%}{x.caught:>8}")
single = mon.watch_record(p, w)
(ROOT / "code" / "24" / "14_watchlist.json").write_text(json.dumps(
    {"sweep": sweep,
     "triggers": [{"flag": x.flag, "hit": round(x.hit_rate, 4),
                   "caught": int(x.caught), "months": int(x.months)}
                  for x in pd.concat([single, r]).itertuples()]},
    indent=1) + "\n")
