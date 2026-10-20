# Ballast v0.9: the stress test saved for the risk pack, read back,
# and one scenario run again to prove the files are what it gives.
# timeout: 900
import fernhill
from ballast import stress
from ballast.config import ROOT

con = fernhill.connect()
saved = stress.load()
print("data/ballast/stress/ holds:")
for f in sorted((ROOT / "data" / "ballast" / "stress").iterdir()):
    print(f"  {f.name:<34}{f.stat().st_size / 1024:>7.1f} KB")
y = saved["years"]
print(f"{len(y)} scenario-years, {len(saved['products'])} product-"
      f"years, {len(saved['paths'])} path-months")

inp = stress.inputs(con)
again = stress.project(inp, stress.paths(con)["stress_2026"],
                       "stress_2026")["years"]
old = y[y.scenario == "stress_2026"].reset_index(drop=True)
cols = ["loss", "provision", "charge", "nii", "cet1"]
diff = (again[cols] - old[cols]).abs().to_numpy().max()
print(f"stress_2026 run again: largest difference {diff:.2f} cents")

s = saved["summary"]
print(f"\nCET1 requirement {s['requirement']:.1%}; lowest CET1 ratio, "
      "2026-2028:")
for k in s["trough_sa"]:
    g = y[y.scenario == k]
    yr = int(g.year[g.cet1_sa.idxmin()])
    print(f"  {k:<12}{s['trough_sa'][k]:>7.1%} standardised in {yr}, "
          f"{s['trough_irb'][k]:>6.1%} on IRB")
r = saved["reverse"]
for k, v in r.items():
    if k != "target":
        print(f"  reverse, {k} shape: x {v['k']:.2f}, unemployment "
              f"{v['peak_u']:.2f}%")
