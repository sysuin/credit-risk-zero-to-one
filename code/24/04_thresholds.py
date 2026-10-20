# Which alarm would have rung for version 3, and how often would it
# have rung for nothing? Six rules, 30 quiet months and 9 after.
import pandas as pd

from ballast import data
from ballast import monitoring as mon
from ballast.decision import policy

raw = data.load_applications(unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")
         & (raw["app_date"].astype(str) < "2020-04-01")]
month = pd.to_datetime(pl["app_date"].astype("datetime64[s]")) \
    .dt.to_period("M")
score = pl["mark1_score"].astype(float)
roll = mon.monthly_stability(score, month)
fixed = mon.monthly_stability(score, month,
                              reference=(month <= "2016-12"))
bureau = policy.mark1_lines(pl)["bureau_score"]
rows = []
for m in sorted(month[month >= "2017-01"].unique()):
    ref = bureau[(month < m) & (month >= m - 12)]
    now = bureau[month == m]
    bands = len(set(ref) | set(now))
    rows.append({"month": str(m), "csi": mon.category_psi(ref, now),
                 "csi_noise": mon.psi_noise(len(now), len(ref), bands)})
csi = pd.DataFrame(rows)
t = roll.merge(fixed[["month", "psi", "noise"]], on="month",
               suffixes=("", "_fix")).merge(csi, on="month")
t = t[t["month"] >= "2017-01"]
rules = {
    "score PSI >= 0.10, rolling": t["psi"] >= mon.PSI_AMBER,
    "score PSI >= noise, rolling": t["psi"] >= t["noise"],
    "score PSI >= noise, fixed": t["psi_fix"] >= t["noise_fix"],
    "mean shift |z| >= 3, rolling": t["z"].abs() >= mon.Z_ALARM,
    "bureau line >= 0.10, rolling": t["csi"] >= mon.PSI_AMBER,
    "bureau line >= noise, rolling": t["csi"] >= t["csi_noise"],
}
before = (t["month"] < "2019-07").to_numpy()
print("Personal-loan applicants; rolling = the 12 months before;")
print("fixed = 2016's applicants. Noise = the 99% level for the month.")
print(f"{'alarm rule':<31}{'false':>7}{'first':>9}{'rang':>10}")
print(f"{'':<31}{'alarms':>7}{'after':>9}{'Jul-Mar':>10}")
for name, ring in rules.items():
    r = ring.to_numpy()
    after = t["month"].to_numpy()[~before][r[~before]]
    first = after[0] if len(after) else "never"
    print(f"{name:<31}{r[before].sum():>7}{first:>9}"
          f"{r[~before].sum():>5} of {(~before).sum()}")
print(f"(false alarms counted over {before.sum()} months, Jan 2017 - "
      f"Jun 2019)")
j = t[t["month"] == "2019-07"].iloc[0]
print(f"July 2019: bureau line {j.csi:.3f} against noise "
      f"{j.csi_noise:.3f}; score z {j.z:.1f}")
