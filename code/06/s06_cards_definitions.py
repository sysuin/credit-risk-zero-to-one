# Exercise 3: stitched card vintages under both definitions.
import fernhill
from ballast import performance as perf

con = fernhill.connect()
t = {d: perf.vintage_table(con, "card", perf.default_episodes(con, d))
     for d in perf.DEFINITIONS}
print(f"{'opened':<8}{'dpd90 m12':>10}{'dod m12':>9}"
      f"{'dpd90 m36':>11}{'dod m36':>9}")
for c in t["dpd90"].index[:-1]:
    cells = ""
    for k in (12, 36):
        for d in perf.DEFINITIONS:
            v = t[d].loc[c, k]
            w = 10 if (d == "dpd90" and k == 12) else 9
            w = 11 if (d == "dpd90" and k == 36) else w
            cells += f"{v:>{w}.2%}" if v == v else f"{'.':>{w}}"
    print(f"{c:<8}{cells}")
