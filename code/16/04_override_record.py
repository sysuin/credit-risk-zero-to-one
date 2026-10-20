# The record of the holds: what happened in the year after an analyst
# kept a grade the model wanted to change.
import fernhill
from ballast.commercial import rating as rt

con = fernhill.connect()
m = rt.moves(rt.reviews(con))
m = m[m.window_complete & (m.wanted != 0)]
m["pd_kept"] = m.grade.map(rt.pd_of)
m["pd_model"] = m.model_grade.map(rt.pd_of)
print("reviews where the model wanted a move (complete years)")
print(f"{'model':<11}{'analyst':<9}{'reviews':>8}{'defaults':>9}"
      f"{'rate':>7}{'PD given':>10}{'model PD':>10}")
for side, sel in (("downgrade", m.wanted > 0),
                  ("upgrade", m.wanted < 0)):
    for what, h in (("moved", False), ("held", True)):
        g = m[sel & (m.held_found == h)]
        print(f"{side:<11}{what:<9}{len(g):>8}"
              f"{g.default_12m.sum():>9}{g.default_12m.mean():>7.1%}"
              f"{g.pd_kept.mean():>10.1%}{g.pd_model.mean():>10.1%}")

d = m[m.default_12m == 1]
print(f"\nof these, {len(d)} defaulted within the year; the grade"
      f" was held in {d.held_found.sum()}")
print(f"{'client':<8}{'review':>7}{'was':>6}{'model':>7}{'kept':>6}"
      f"{'defaulted':>12}")
for _, r in d[d.held_found].sort_values("review_date").iterrows():
    when = f"{r.default_month:%b %Y}"
    print(f"{r.company_id:<8}{r.review_date.year:>7}{r.previous:>6}"
          f"{r.model_grade:>7}{r.grade:>6}{when:>12}")
