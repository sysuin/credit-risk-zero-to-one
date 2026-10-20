# Checking the decision against the answer. The truth is read here,
# and only here, to see how a choice made without it turned out.
import numpy as np

import fernhill
from ballast.decision import strategy
from ballast.models import gbm
from ballast.scorecard import metrics, points, reject, sample

a = reject.applicants()
a = a[~a["policy"]].copy()
truth = fernhill.connect(truth=True).execute("""
    SELECT app_id, bad_12m_if_booked::DOUBLE AS would_be_bad
    FROM origination ORDER BY app_id""").df()
worst = sample.load_sample()[["app_id", "worst_missed"]]
a = a.merge(truth, on="app_id", how="left").merge(worst, on="app_id",
                                                  how="left")
# Booked loans: Fernhill's own outcome (two missed counts as not bad).
booked_bad = (a["worst_missed"] >= 3).astype(float)
a["truth"] = np.where(a["known"], booked_bad, a["would_be_bad"])
a["mark2"] = points.load_scorecard().score(a)
a["mark2r"] = reject.load_refit("mark2_retro_ws").scorecard().score(a)
a["gbm"] = gbm.load().score(a)
SCORES = {"Mark I": "mark1_score", "Mark II": "mark2",
          "Mark II-R": "mark2r", "challenger": "gbm"}

print("True Gini, every applicant who passed the rules")
print(f"  {'':<12}" + "".join(f"{k:>11}" for k in SCORES))
for split in ("holdout", "out_of_time"):
    d = a[a["split"] == split]
    y = d["truth"].astype(int)
    print(f"  {split:<12}" + "".join(
        f"{metrics.gini(d[c], y):>11.3f}" for c in SCORES.values()))

d = a[a["split"] == "out_of_time"].reset_index(drop=True)
y = d["truth"].to_numpy()
fern = d["outcome"].ne("declined").to_numpy()
share = fern.mean()
print(f"\nOut of time, approving {share:.1%}: true bad rate")
print(f"  {'Fernhill':<12}{y[fern].mean():>7.2%}")
for k, c in SCORES.items():
    print(f"  {k:<12}{reject.approve_best(-d[c], y, share):>7.2%}")

promise = np.asarray(points.bad_rate_at(d["mark2r"]))
new = (d["mark2r"] >= 554).to_numpy()
cells = {"both approve": new & fern, "only Mark II-R": new & ~fern,
         "only Fernhill": ~new & fern}
print("\nMark II-R at 554 against Fernhill's decisions")
print(f"  {'':<16}{'people':>7}{'true':>8}{'promised':>10}")
for name, m in cells.items():
    print(f"  {name:<16}{int(m.sum()):>7,}{y[m].mean():>8.1%}"
          f"{promise[m].mean():>10.1%}")
edge = (d["mark2r"] >= 554) & (d["mark2r"] < 559)
print(f"  {'554 to 558':<16}{int(edge.sum()):>7,}{y[edge].mean():>8.1%}"
      f"{promise[edge].mean():>10.1%}")

con = fernhill.connect()
eco = strategy.loan_economics(con, "personal")
s = sample.load_sample()
s = s[s["app_date"].astype(str).between("2019-01-01", "2021-12-31")]
e = s[["account_id", "outcome"]].merge(eco, on="account_id")
earns = e.loc[e["outcome"] == "good", "profit"].mean() / 100
costs = -e.loc[e["outcome"] == "bad", "profit"].mean() / 100
print("\nIf every approval took the loan, per 1,000 applicants:")
for name, ap in (("Fernhill", fern), ("Mark II-R at 554", new)):
    bads = y[ap].sum() / len(y) * 1000
    goods = ap.sum() / len(y) * 1000 - bads
    print(f"  {name:<18}{goods + bads:>5.0f} loans, true bad rate "
          f"{y[ap].mean():.2%}, ${goods * earns - bads * costs:,.0f}")
