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
# Each PD at each pair of levels: (column, PD, amber, red)
RUNS = [("PIT 95/99.9", "pit", 0.95, 0.999),
        ("PIT 90/99", "pit", 0.90, 0.99),
        ("TTC 95/99.9", "ttc", 0.95, 0.999),
        ("TTC 90/99", "ttc", 0.90, 0.99)]
header = f"{'year':<6}{'seen':>6}"
for column, *_ in RUNS:
    header += f"{column:>14}"
print(header)
for y, g in bt.groupby("year"):
    n, d = len(g), int(g["y"].sum())
    row = f"{y:<6}{d:>6}"
    for _, k, amber, red in RUNS:
        # the module reads its two levels from these settings
        vd.AMBER, vd.RED = amber, red
        row += f"{vd.traffic_light(n, d, g[k].mean()):>14}"
    print(row)
