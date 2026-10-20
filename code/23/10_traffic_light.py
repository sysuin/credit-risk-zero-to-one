# The 12-month PD backtested year by year: each year's PDs from a
# model refitted without that year's defaults, against the defaults
# the year brought.
import json
from pathlib import Path

import fernhill
from _cache import loans
from ballast import capital
from ballast import validation as vd
from ballast.parameters import pd as pdm

con = fernhill.connect()
panel = pdm.account_months(con, loans(con))
bt = vd.pd_backtest(panel, range(2017, 2026),
                    pdm.long_run_unemployment(con),
                    pdm.unemployment(con))
COLS = {"pit": "known u", "flat": "no change", "ttc": "TTC"}
print("Performing personal loans on 31 December, defaults in the")
print("year, and the defaults each PD expected, with its light")
print(f"{'year':<6}{'loans':>6}{'seen':>6}"
      + "".join(f"{v:>13}" for v in COLS.values()) + f"{'corr.':>8}")
fig, rhos = [], []
for y, g in bt.groupby("year"):
    n, d = len(g), int(g["y"].sum())
    row = {"year": int(y), "n": n, "d": d}
    for k in COLS:
        p = g[k].mean()
        row[k] = float(g[k].sum())
        row[k + "_light"] = vd.traffic_light(n, d, p)
        row[k + "_lim"] = [round(x, 1) for x in vd.limits(n, p)]
    rho = float(capital.correlation(g["ttc"].mean(), "other_retail"))
    rhos.append(rho)
    row["ttc_corr"] = vd.traffic_light(n, d, g["ttc"].mean(), rho)
    fig.append(row)
    print(f"{y:<6}{n:>6,}{d:>6}" + "".join(
        f"{row[k]:>7.1f}{row[k + '_light']:>6}" for k in COLS)
        + f"{row['ttc_corr']:>8}")
for k, v in COLS.items():
    lights = [r[k + "_light"] for r in fig]
    print(f"{v + ':':<11}" + ", ".join(
        f"{lights.count(c)} {c}" for c in ("green", "amber", "red")))
print("Lights at 95% and 99.9% of the binomial; corr.: the TTC PD")
print("with defaults correlated as the IRB formula has them,")
print(f"at rho {min(rhos):.3f} to {max(rhos):.3f}")
Path(__file__).with_suffix(".json").write_text(json.dumps(fig) + "\n")
