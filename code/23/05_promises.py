# Calibration, re-performed: does Mark II-R's scale keep its promises,
# band by band, on the booked loans of 2023-24 and on 2023's
# applicants with an outcome seen by Fernhill or the bureau?
import numpy as np
import pandas as pd

from ballast.scorecard import metrics, points, reject

a = reject.applicants()
a = a[~a["policy"]].merge(reject.retro(), on="app_id", how="left")
a["score"] = reject.load_refit("mark2_retro_ws").scorecard().score(a)
a["promised"] = points.bad_rate_at(a["score"])
seen_else = a["opened_elsewhere"].fillna(False).astype(bool)
a["seen"] = np.where(a["known"], a["bad"],
                     np.where(seen_else, a["bad_elsewhere"], np.nan))
year = pd.to_datetime(a["app_date"].astype("datetime64[s]")).dt.year
EDGES = [540, 560, 580, 600, 620]
# The two samples: booked loans only, then booked plus bureau-seen
late = a["split"] == "out_of_time"
SAMPLES = {"Booked, 2023 to mid-2024": late & a["known"],
           "Booked and bureau-seen, 2023": late & (year == 2023)}
for name, m in SAMPLES.items():
    d = a[m & a["seen"].notna()]
    y = d["seen"].astype(int)
    # Promised against seen bad rates, band by band, with p-values
    t = metrics.calibration(d["score"], y, d["promised"], EDGES)
    hl, df, p = metrics.hosmer_lemeshow(d["promised"], y)
    print(f"{name}: {len(d):,} loans,\n  promised "
          f"{d['promised'].mean():.2%}, seen {y.mean():.2%}")
    print(f"  {'band':<9}{'loans':>7}{'promised':>10}{'seen':>8}"
          f"{'expected':>10}{'bads':>6}{'p':>8}")
    for r in t.itertuples():
        print(f"  {r.band:<9}{r.loans:>7,}{r.predicted:>10.2%}"
              f"{r.observed:>8.2%}{r.expected:>10.1f}{r.bads:>6}"
              f"{r.p_value:>8.3f}")
    print(f"  Hosmer-Lemeshow {hl:.1f} on {df} df, p {p:.4f}\n")
