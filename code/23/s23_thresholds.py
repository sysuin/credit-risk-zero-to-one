# Exercise 23.2: the traffic light with tighter thresholds, 90% and
# 99%, on the same yearly backtest.
import fernhill
from _cache import loans
from ballast import validation as vd
from ballast.parameters import pd as pdm

con = fernhill.connect()
panel = pdm.account_months(con, loans(con))
bt = vd.pd_backtest(panel, range(2017, 2026),
                    pdm.long_run_unemployment(con))
print(f"{'year':<6}{'seen':>6}" + "".join(
    f"{k + ' ' + lv:>14}" for k in ("PIT", "TTC")
    for lv in ("95/99.9", "90/99")))
for y, g in bt.groupby("year"):
    n, d = len(g), int(g["y"].sum())
    out = []
    for k in ("pit", "ttc"):
        for amber, red in ((0.95, 0.999), (0.90, 0.99)):
            vd.AMBER, vd.RED = amber, red
            out.append(vd.traffic_light(n, d, g[k].mean()))
    print(f"{y:<6}{d:>6}" + "".join(f"{x:>14}" for x in out))
