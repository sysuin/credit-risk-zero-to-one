# Exercise 18.3: cards by Mark I tier, Kaplan-Meier against cumulative
# incidence at 36 months, and how often cards close.
import fernhill
from ballast.parameters import pd as pdm

con = fernhill.connect()
d = pdm.durations(con, "card")
print(f"{'tier':<9}{'cards':>7}{'closed':>8}{'KM 36':>8}{'CI 36':>8}"
      f"{'KM/CI':>7}")
for b in sorted(d.band.unique(), key=pdm._band_key):
    g = d[d.band == b]
    t = pdm.life_table(g, 36)
    km, ci = pdm.kaplan_meier(t)[36], pdm.cumulative_incidence(t)[36]
    print(f"{b:<9}{len(g):>7,}{(g.event == 2).mean():>8.0%}"
          f"{km:>8.1%}{ci:>8.1%}{km / ci:>7.2f}")
p = pdm.durations(con, "personal")
t = pdm.life_table(p, 36)
km, ci = pdm.kaplan_meier(t)[36], pdm.cumulative_incidence(t)[36]
print(f"personal {len(p):>7,}{(p.event == 2).mean():>8.0%}"
      f"{km:>8.1%}{ci:>8.1%}{km / ci:>7.2f}")
