# Exercise 18.5: a new 60-month personal loan in band 580-599, opened
# in January 2026, under each scenario: 12-month and lifetime PD.
import numpy as np
import pandas as pd

import fernhill
from ballast.config import AS_OF
from ballast.parameters import pd as pdm

con = fernhill.connect()
model = pdm.load_hazards()["personal"]
print(f"{'scenario':<13}{'u 2026':>7}{'u 2026-30':>10}{'12 months':>11}"
      f"{'60 months':>11}")
for s in ["upside", "base", "downside", "severe", "stress_2026"]:
    u = pdm.unemployment(con, s)
    path = u[u.index > pd.Timestamp(AS_OF)].to_numpy()[:60]
    ts = model.term_structure("580-599", path)
    print(f"{s:<13}{path[:12].mean():>7.2f}{path.mean():>10.2f}"
          f"{ts.cumulative_pd[11]:>11.2%}{ts.cumulative_pd[59]:>11.2%}")
lr = pdm.load_json("pd_hazard.json")["long_run_unemployment"]
ts = model.term_structure("580-599", np.full(60, lr))
print(f"{'long run':<13}{lr:>7.2f}{lr:>10.2f}"
      f"{ts.cumulative_pd[11]:>11.2%}{ts.cumulative_pd[59]:>11.2%}")
