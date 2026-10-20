# The loans just above Mark II-R's cut-off of 554: what they promised
# and did, and what the 2025 loans in that band show so far.
import pandas as pd

import fernhill
from ballast import data
from ballast import monitoring as mon
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import points

con = fernhill.connect()
p = pol.load_policy()
card = engine.load_champion(p)
raw = data.load_applications(con, unknowns=False)
booked = raw[raw["product"].astype(str).eq("personal")
             & raw["outcome"].astype(str).eq("booked")]
s = pd.DataFrame({"account_id": booked["account_id"].astype(str),
                  "app_date": booked["app_date"].astype(str),
                  "score": card.score(engine.prepare(booked))})
e = mon.early_accounts(con, "personal")
s = s.merge(e, left_on="account_id", right_on="root_id")
EDGES = [0, p.cutoff, 570, 600, 999]
NAMES = [f"below {p.cutoff}", f"{p.cutoff}-569", "570-599", "600+"]
s["band"] = pd.cut(s["score"], EDGES, right=False, labels=NAMES)
s["promised"] = points.bad_rate_at(s["score"])
old = s[(s.app_date >= "2023-01-01") & (s.app_date < "2024-07-01")]
new = s[(s.app_date >= "2025-01-01") & (s.seen >= 3)]
print(f"Personal loans by Mark II-R band (cut-off {p.cutoff})")
print(f"{'':<11}{'2023 to mid-2024':>30}{'2025, 3+ months':>21}")
print(f"{'band':<11}{'loans':>7}{'promised':>9}{'90+ m12':>8}"
      f"{'30+ m3':>7}{'loans':>9}{'30+ m3':>8}{'z':>5}")
for b in NAMES:
    o, n = old[old.band == b], new[new.band == b]
    z = mon.mean_shift_z(o["e3"], n["e3"])
    print(f"{b:<11}{len(o):>7,}{o.promised.mean():>9.2%}"
          f"{o.b12.mean():>8.2%}{o.e3.mean():>7.2%}{len(n):>9,}"
          f"{n.e3.mean():>8.2%}{z:>5.1f}")
print(f"{'all':<11}{len(old):>7,}{old.promised.mean():>9.2%}"
      f"{old.b12.mean():>8.2%}{old.e3.mean():>7.2%}{len(new):>9,}"
      f"{new.e3.mean():>8.2%}")
