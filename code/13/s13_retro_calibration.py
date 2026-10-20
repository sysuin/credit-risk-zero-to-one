# Exercise 13.1: the gender test of calibration, with the bureau's retro
# outcomes added to the booked loans (2019-2023 applicants).
import numpy as np

from ballast import fairness
from ballast.scorecard import points, reject

a = reject.applicants()
a = a[~a["policy"]].merge(reject.retro(), on="app_id", how="left")
a = a.merge(fairness.monitoring(), on="app_id", validate="1:1")
elsewhere = a["opened_elsewhere"].fillna(False).astype(bool)
a["seen"] = np.where(a["known"], a["bad"],
                     np.where(elsewhere, a["bad_elsewhere"], np.nan))
year = a["app_date"].astype(str).str[:4].astype(int)
card = reject.load_refit("mark2_retro_ws").scorecard()
a["promised"] = points.bad_rate_at(card.score(a))
for name, m in (("booked only", a["known"]),
                ("booked + retro", a["known"] | elsewhere)):
    x = a[m & a["seen"].notna() & a["gender"].isin(["F", "M"])
          & year.between(2019, 2023)]
    e = fairness.group_effect(x["promised"], x["seen"],
                              x["gender"].eq("F"))
    print(f"{name:<16}{len(x):>7,} rows {int(x['seen'].sum()):>5} bad"
          f"  woman {e['coef']:+.3f} (p {e['p']:.3f})")
