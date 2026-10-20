# Lifetime PD by score band four ways: the naive share, Kaplan-Meier
# (closures censored), cumulative incidence (closure a competing exit)
# and the vintage curve of cohorts old enough to have finished.
import fernhill
from ballast.parameters import pd as pdm

con = fernhill.connect()
d = pdm.durations(con, "personal")
n = d.event.value_counts()
print(f"{len(d):,} personal loans: {n[1]:,} defaulted, {n[2]:,} "
      f"closed first,\n{n[0]:,} still open and not in default "
      "on 31 December 2025 (censored)")
old = d[d.start.dt.year <= 2019]
print(f"Vintage: the {len(old):,} loans opened 2016-2019, "
      f"all seen for 72 months\n")
print(f"{'band':<9}{'loans':>6}{'naive':>7}  {'month':>5}{'KM':>7}"
      f"{'CI':>7}{'vintage':>9}")
for b in sorted(d.band.unique(), key=pdm._band_key):
    g = d[d.band == b]
    t = pdm.life_table(g, 60)
    km, ci = pdm.kaplan_meier(t), pdm.cumulative_incidence(t)
    o = old[old.band == b]
    for i, m in enumerate((12, 36, 60)):
        vint = ((o.event == 1) & (o.t <= m)).mean()
        head = (f"{b:<9}{len(g):>6,}{(g.event == 1).mean():>7.1%}"
                if i == 0 else " " * 22)
        print(f"{head}  {m:>5}{km[m]:>7.1%}{ci[m]:>7.1%}{vint:>9.1%}")
t = pdm.life_table(d, 60)
print(f"\nAll loans at 60 months: KM {pdm.kaplan_meier(t)[60]:.1%}, "
      f"CI {pdm.cumulative_incidence(t)[60]:.1%}, vintage "
      f"{((old.event == 1) & (old.t <= 60)).mean():.1%}\n"
      f"Loans of 2016-2019 that closed before defaulting: "
      f"{(old.event == 2).mean():.0%}")
