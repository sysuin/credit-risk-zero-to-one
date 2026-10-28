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
for year, g in h.groupby("year"):
    worse = g[g.direction == "down"]
    better = g[g.direction == "up"]
    print(f"{year:<8}{len(worse):>17}{worse.held_found.mean():>6.0%}"
          f"{len(better):>19}{better.held_found.mean():>6.0%}")
worse = h[h.direction == "down"]
better = h[h.direction == "up"]
print(f"{'all':<8}{len(worse):>17}{worse.held_found.mean():>6.0%}"
      f"{len(better):>19}{better.held_found.mean():>6.0%}")

done = h[h.window_complete & (h.direction == "down")]
print("\nmodel said worse, year after the review complete:")
for held, g in done.groupby("held_found"):
    name = "held" if held else "moved"
    grade_pd = g.grade.map(gv.MASTER_SCALE).mean()
    model_pd = g.model_grade.map(gv.MASTER_SCALE).mean()
    print(f"  {name:<6}{len(g):>4},{g.default_12m.sum():>4} "
          f"defaults ({g.default_12m.mean():.1%}); PD: grade "
          f"{grade_pd:.2%}, model {model_pd:.2%}")
