# A behavioural score for personal loans and cards, fitted on quarter
# ends 2017-2021 and tested on 2022-2024 against the application score.
import datetime as dt

import fernhill
from ballast import monitoring as mon
from ballast.scorecard import metrics

con = fernhill.connect()
months = mon.quarter_ends(dt.date(2017, 12, 31), dt.date(2024, 12, 31))
f = mon.behaviour_frame(con, months)
dev = f[f["month"].astype(str) < "2022-01-01"]
test = f[f["month"].astype(str) >= "2022-01-01"]
print(f"{'':<10}{'account-quarters':>17}{'bad in 12m':>12}"
      f"{'test rows':>11}{'bad':>7}")
for p, g in f.groupby("product"):
    t = test[test["product"] == p]
    print(f"{p:<10}{len(g):>17,}{g['bad'].mean():>12.2%}"
          f"{len(t):>11,}{t['bad'].mean():>7.2%}")
fits = {}
for p in ("card", "personal"):
    fits[p] = (mon.fit_behaviour(dev, p, application=False),
               mon.fit_behaviour(dev, p))
print("\nGini on the test quarters (2022-2024)")
print(f"{'':<10}{'application':>13}{'account':>10}{'history +':>13}")
print(f"{'':<10}{'score':>13}{'history':>10}{'application':>13}")
for p, (hist, both) in fits.items():
    t = test[test["product"] == p]
    y = t["bad"]
    print(f"{p:<10}{metrics.gini(t['application_score'], y):>13.3f}"
          f"{metrics.gini(hist.score(t), y):>10.3f}"
          f"{metrics.gini(both.score(t), y):>13.3f}")
print("\nGini by months on book, test quarters (loan = personal loan)")
t = test.assign(score=0)
for p, (hist, both) in fits.items():
    m = t["product"] == p
    t.loc[m, "score"] = both.score(t[m])
t["mob"] = mon.behaviour_bins(t, ["months_on_book"])["months_on_book"]
print(f"{'':<26}{'application':>13}{'behaviour':>13}")
print(f"{'months':<10}{'rows':>9}{'bad':>7}{'card':>7}{'loan':>6}"
      f"{'card':>7}{'loan':>6}")
for b, g in t.groupby("mob", observed=True):
    app, beh = [], []
    for p in fits:
        h = g[g["product"] == p]
        app.append(metrics.gini(h["application_score"], h["bad"]))
        beh.append(metrics.gini(h["score"], h["bad"]))
    print(f"{b:<10}{len(g):>9,}{g['bad'].mean():>7.2%}"
          f"{app[0]:>7.3f}{app[1]:>6.3f}{beh[0]:>7.3f}{beh[1]:>6.3f}")
path = mon.save_behaviour([fits["card"][1], fits["personal"][1]])
print(f"saved {path.relative_to(path.parents[3])}")
