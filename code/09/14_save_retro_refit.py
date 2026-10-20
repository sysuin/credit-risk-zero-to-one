# Ballast's reject inference end to end, saved as a candidate refit.
import numpy as np

from ballast.config import ROOT
from ballast.scorecard import model, reject, sample, woe

a = reject.applicants()
dev = a[a["period"] == "development"]
print("development applicants by outcome (Chapter 7's funnel):")
for out, n in dev["outcome"].value_counts().sort_index().items():
    print(f"  {out:<14}{n:>7,}")
print(f"  {'all':<14}{len(dev):>7,}")
f = reject.frames(a)
print("frames: " + ", ".join(f"{k} {len(v):,}" for k, v in f.items()))

ws = woe.load_binset(sample.MARK2 / "bins.json")["worst_status_24m"]
cols = model.CHARACTERISTICS + ["worst_status_24m"]
t = reject.training_set("bureau retro", f["accepts"], f["unknown"],
                        retro_rows=reject.retro())
r = reject.fit(t, t["bad"], t["weight"], cols=cols,
               template=reject.mark2_bins() | {"worst_status_24m": ws})
path = reject.save_refit(
    r, "mark2_retro_ws",
    note="Mark II's nine and worst status, refitted on booked loans "
         "and bureau-retro outcomes of 2019-2022 unknowns; a "
         "candidate, not in use")
back = reject.load_refit("mark2_retro_ws")
gap = np.abs(back.p_bad(f["oot"]) - r.p_bad(f["oot"])).max()
print(f"saved {path.relative_to(ROOT)}, "
      f"{path.stat().st_size:,} bytes")
print(f"fitted on {len(t):,} rows, {t['bad'].mean():.1%} bad")
print(f"reloaded: largest difference in p(bad) {gap:.1e}")
card = back.scorecard()
line = card.table[card.table["characteristic"] == "worst_status_24m"]
print(f"base {card.base}; worst status line: " + ", ".join(
    f"{b} {p}" for b, p in zip(line["bin"], line["points"])))
