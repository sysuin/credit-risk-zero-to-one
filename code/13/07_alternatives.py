# Less discriminatory alternatives: Mark II-R refitted without income,
# and without the two lines that measure time, on the same rows.
import numpy as np
import pandas as pd

from ballast import fairness
from ballast.decision import strategy
from ballast.scorecard import metrics, model, reject, sample, woe

a = reject.applicants()
f = reject.frames(a)
ws = woe.load_binset(sample.MARK2 / "bins.json")["worst_status_24m"]
tmpl = reject.mark2_bins() | {"worst_status_24m": ws}
cols = model.CHARACTERISTICS + ["worst_status_24m"]
t = reject.training_set("bureau retro", f["accepts"], f["unknown"],
                        retro_rows=reject.retro())
DROP = {"Mark II-R": [], "no income": ["income"],
        "no time lines": ["oldest_account_months", "address_months"]}
fits = {k: reject.fit(t, t["bad"], t["weight"], template=tmpl,
                      cols=[c for c in cols if c not in v])
        for k, v in DROP.items()}

x = a[~a["policy"]].merge(reject.retro(), on="app_id", how="left")
x = x.merge(fairness.monitoring(), on="app_id", validate="1:1")
seen_else = x["opened_elsewhere"].fillna(False).astype(bool)
x["seen"] = np.where(x["known"], x["bad"],
                     np.where(seen_else, x["bad_elsewhere"], np.nan))
year = pd.to_datetime(x["app_date"].astype("datetime64[s]")).dt.year
oot_rows = x["split"] == "out_of_time"
hold_rows = x["split"] == "holdout"
SAMPLES = {"booked, OOT": oot_rows & x["known"],
           "+ retro, holdout": hold_rows & (year >= 2019),
           "+ retro, 2023": oot_rows & (year == 2023)}
for k, r in fits.items():
    x[k] = r.scorecard().score(x)     # whole points, as decided
print(f"{'Gini':<18}" + "".join(f"{k:>15}" for k in fits))
for name, m in SAMPLES.items():
    dd = x[m & x["seen"].notna()]
    y = dd["seen"].astype(int)
    print(f"{name:<18}" + "".join(f"{metrics.gini(dd[k], y):>15.3f}"
                                  for k in fits))

oot = x[x["split"] == "out_of_time"]
band = fairness.age_band(oot["age"]).astype(str).to_numpy()
print(f"\nApproving 71.5% of {len(oot):,} applicants, 2023 to mid-2024")
print(f"{'':<18}" + "".join(f"{k:>15}" for k in fits))
rows = {k: strategy.top_share(oot[k].to_numpy(), 0.715) for k in fits}
air = {k: fairness.adverse_impact_ratio(v, oot["gender"], "F", "M")
       for k, v in rows.items()}
print(f"{'women / men':<18}" + "".join(f"{air[k]:>15.3f}"
                                       for k in fits))
for b in ("18-24", "25-34", "35-49", "65+"):
    print(f"{'aged ' + b:<18}" + "".join(
        f"{rows[k][band == b].mean():>15.1%}" for k in fits))
k = x[x["known"] & x["bad"].notna()]
decade = (k["age"] - 40) / 10
eff = {n: fairness.group_effect(r.p_bad(k), k["bad"], decade)["coef"]
       for n, r in fits.items()}
print(f"{'decade of age':<18}" + "".join(f"{eff[n]:>+15.3f}"
                                         for n in fits))
print("(on the log odds of booked loans, at the same score)")
