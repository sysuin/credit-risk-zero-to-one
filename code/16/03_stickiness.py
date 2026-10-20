# How the analysts moved their grades, set against where the model
# would have taken them, at every review with a previous grade.
import json

import pandas as pd

import fernhill
from ballast.commercial import rating as rt
from ballast.config import ROOT

con = fernhill.connect()
rv = rt.reviews(con)
m = rt.moves(rv)
print(f"reviews with a previous grade: {len(m):,}")
print(f"held flag in the ratings table agrees with the moves: "
      f"{(m.held == m.held_found).all()}")

t = pd.crosstab(m.wanted.clip(-4, 4), m.moved.clip(-4, 4))
print("\nmodel wanted (rows) against analyst moved (columns),"
      " notches")
print(f"{'':>6}" + "".join(f"{c:>6}" for c in t.columns))
for w, row in t.iterrows():
    print(f"{w:>6}" + "".join(f"{v:>6}" for v in row))

s = rt.stickiness(m)
print(f"\n{'wanted':<9}{'reviews':>8}{'one notch':>11}"
      f"{'to model':>10}{'held':>8}")
for k, r in s.iterrows():
    label = f"{k}+" if k == 4 else str(k)
    print(f"{label:<9}{r.reviews:>8.0f}{r.one_notch:>11.0%}"
          f"{r.to_model:>10.0%}{r.held:>8.0%}")
want = m[m.wanted != 0]
print(f"\nthe model wanted a move in {len(want):,} reviews; "
      f"held in {want.held_found.sum()} ({want.held_found.mean():.1%})")

both = pd.crosstab(rv.grade, rv.model_grade).reindex(
    index=rt.GRADES, columns=rt.GRADES, fill_value=0)
out = ROOT / "code" / "16" / "03_stickiness.json"
out.write_text(json.dumps({"counts": both.values.tolist()}))
