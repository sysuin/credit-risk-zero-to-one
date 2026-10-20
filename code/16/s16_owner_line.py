# Exercise 16.4: SME-1 with its owner line fed version-2 scores, as it
# was built for, on applications from July 2019.
import numpy as np

import fernhill
from ballast.commercial import sme

con = fernhill.connect()
apps = con.execute("SELECT * FROM sme_applications ORDER BY app_id"
                   ).df()
v2_to_v3 = sme.owner_map(apps)
late = apps[(apps.app_date >= "2019-07-01")
            & (apps["product"] != "sme_emergency")].copy()
# back from version 3 to version 2: invert the percentile map
back = np.interp(late.owner_bureau_score, v2_to_v3.to_numpy(),
                 v2_to_v3.index.to_numpy())
late["owner_bureau_score"] = np.round(back).astype(int)
late["rescored"] = sme.sme1_points(late).total
booked = late[late.outcome == "booked"]
lost = booked[booked.rescored < booked.cutoff]
print(f"booked from July 2019 (term and overdraft): {len(booked):,}")
print(f"below the cut-off with version-2 owner points: {len(lost):,}"
      f" ({len(lost) / len(booked):.1%})")
s = sme.sample(con).set_index("app_id")
seen = s.loc[s.index.intersection(booked.app_id)]
gone = seen.index.isin(lost.app_id)
print(f"with a 24-month outcome: {len(seen):,}")
print(f"  bad rate of those lost {seen.bad[gone].mean():.1%}, of those "
      f"kept {seen.bad[~gone].mean():.1%}")
