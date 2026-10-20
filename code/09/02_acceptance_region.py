# Who has an outcome: applicants by Mark I's score minus the cut-off.
import json

import numpy as np

from ballast.config import ROOT
from ballast.scorecard import reject

a = reject.applicants()
dev = a[a["period"] == "development"].copy()
edges = [-60, -40, -20, -10, 0, 10, 20, 40, 60]
dev["band"] = np.searchsorted(edges, dev["margin"], side="right")
names = (["<-60"] + [f"{lo:+d} to {hi - 1:+d}" for lo, hi in
                     zip(edges[:-1], edges[1:])] + ["+60 up"])

print(f"{'margin':<13}{'apps':>7}{'policy':>8}{'score':>7}"
      f"{'walked':>8}{'booked':>8}{'known':>7}")
rows = []
for k, g in dev.groupby("band"):
    pol = int(g["policy"].sum())
    sco = int((g["outcome"].eq("declined") & ~g["policy"]).sum())
    walk = int(g["outcome"].eq("not_taken_up").sum())
    bk = int(g["known"].sum())
    print(f"{names[k]:<13}{len(g):>7,}{pol:>8,}{sco:>7,}{walk:>8,}"
          f"{bk:>8,}{bk / len(g):>7.1%}")
    rows.append({"band": names[k], "policy": pol, "score": sco,
                 "walked": walk, "booked": bk})
n, bk = len(dev), int(dev["known"].sum())
scored = int((dev["outcome"].eq("declined") & ~dev["policy"]).sum())
print(f"{'all':<13}{n:>7,}{int(dev['policy'].sum()):>8,}"
      f"{scored:>7,}"
      f"{int(dev['outcome'].eq('not_taken_up').sum()):>8,}{bk:>8,}"
      f"{bk / n:>7.1%}")
print()
ov = dev[dev["override"].eq("low_side")]
print(f"low-side overrides booked below the refer band: "
      f"{int((ov['known'] & (ov['margin'] < -10)).sum())}")
(ROOT / "code" / "09" / "02_acceptance_region.json").write_text(
    json.dumps(rows, indent=1) + "\n")
