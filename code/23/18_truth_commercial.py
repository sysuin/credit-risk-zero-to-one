# The commercial grades against the answer: each client's true one-year
# PD at its review, set beside the three opinions a validator can see,
# and beside the analysts' holds.
import numpy as np
import pandas as pd

import fernhill
from ballast.commercial import rating as rt

con = fernhill.connect()
rv = rt.reviews(con)
dev = rv[rv["window_complete"]].copy()
dev["cv_pd"] = rt.cross_validate(rt.features(dev), dev["default_12m"],
                                 dev["review_date"].dt.year,
                                 rt.load_model().penalty)
truth = fernhill.connect(truth=True)            # the answer
t = truth.execute("""SELECT company_id, month, pd_1y
                     FROM corporate_pd ORDER BY 1, 2""").df()
t["month"] = pd.to_datetime(t["month"])
dev["month"] = dev["review_date"] + pd.offsets.MonthEnd(0)
dev = dev.merge(t, on=["company_id", "month"], how="left",
                validate="1:1")
lt = np.log(dev["pd_1y"].clip(lower=1e-5))
print(f"{len(dev):,} reviews with a true PD; correlation of each "
      "opinion's\nlog PD with the log of the true PD")
for name, p in (("Ballast model (out of year)", dev["cv_pd"]),
                ("Fernhill model grade",
                 dev["model_grade"].map(rt.pd_of)),
                ("analysts' grade", dev["grade"].map(rt.pd_of))):
    print(f"  {name:<28}{np.corrcoef(np.log(p), lt)[0, 1]:>6.3f}")

m = rt.moves(rv)
m = m[m["window_complete"] & (m["wanted"] != 0)].copy()
m["month"] = m["review_date"] + pd.offsets.MonthEnd(0)
m = m.merge(t, on=["company_id", "month"], how="left", validate="1:1")
print(f"\n{'model wanted':<13}{'analyst':<9}{'reviews':>8}"
      f"{'grade PD':>10}"
      f"{'model PD':>10}{'true PD':>9}")
for side, sel in (("downgrade", m["wanted"] > 0),
                  ("upgrade", m["wanted"] < 0)):
    for what, h in (("moved", False), ("held", True)):
        g = m[sel & (m["held_found"] == h)]
        print(f"{side:<13}{what:<9}{len(g):>8}"
              f"{g['grade'].map(rt.pd_of).mean():>10.2%}"
              f"{g['model_grade'].map(rt.pd_of).mean():>10.2%}"
              f"{g['pd_1y'].mean():>9.2%}")
