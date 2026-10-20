# Commercial analysts' holds: reviews where Fernhill's rating model
# wanted a grade to move and the analyst kept it, by year and direction,
# with what followed.
import fernhill
from ballast import governance as gv
from ballast.commercial import rating as rt

con = fernhill.connect()
h = gv.holds(rt.reviews(con))
print(f"{'review':<8}{'model said worse':>17}{'held':>6}"
      f"{'model said better':>19}{'held':>6}")
for y, g in h.groupby("year"):
    d, u = g[g.direction == "down"], g[g.direction == "up"]
    print(f"{y:<8}{len(d):>17}{d.held_found.mean():>6.0%}"
          f"{len(u):>19}{u.held_found.mean():>6.0%}")
print(f"{'all':<8}{(h.direction == 'down').sum():>17}"
      f"{h[h.direction == 'down'].held_found.mean():>6.0%}"
      f"{(h.direction == 'up').sum():>19}"
      f"{h[h.direction == 'up'].held_found.mean():>6.0%}")

done = h[h.window_complete & (h.direction == "down")]
print("\nmodel said worse, year after the review complete:")
for held, g in done.groupby("held_found"):
    name = "held" if held else "moved"
    print(f"  {name:<6}{len(g):>4},{g.default_12m.sum():>4} "
          f"defaults ({g.default_12m.mean():.1%}); PD: grade "
          f"{g.grade.map(gv.MASTER_SCALE).mean():.2%}, model "
          f"{g.model_grade.map(gv.MASTER_SCALE).mean():.2%}")
