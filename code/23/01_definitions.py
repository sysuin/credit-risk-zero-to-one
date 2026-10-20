# The validator's first question: is Mark II-R's bad flag the event
# the PD and the provision count? Every booked loan in Mark II's
# sample, flagged both ways over its first twelve months.

import fernhill
from _cache import loans
from ballast import performance as perf
from ballast.scorecard import metrics, reject, sample

con = fernhill.connect()
s = sample.load_sample()
s["score"] = reject.load_refit("mark2_retro_ws").scorecard().score(s)
s = s.merge(loans(con)[["account_id", "d12"]], on="account_id",
            validate="1:1")
eps = perf.default_episodes(con, "dod2021", products=["personal"])
first = perf.first_defaults(eps)[["account_id", "trigger"]]
s = s.merge(first, on="account_id", how="left")

print(f"{len(s):,} booked loans, applied 2016 to mid-2024")
print(f"{'Mark II-R label':<17}{'loans':>8}{'2021 default in 12m':>21}"
      f"{'by bankruptcy':>15}")
for lab in ("good", "indeterminate", "bad"):
    g = s[s["outcome"] == lab]
    d = g[g["d12"] == 1]
    print(f"{lab:<17}{len(g):>8,}{len(d):>21,}"
          f"{(d['trigger'] == 'bankruptcy').sum():>15,}")
bk = (s["d12"] == 1) & (s["trigger"] == "bankruptcy")
print(f"{'all':<17}{len(s):>8,}{s['d12'].sum():>21,}{bk.sum():>15,}")

print(f"\n{'Gini of Mark II-R':<20}{'loans':>7}{'on its bad':>12}"
      f"{'on 2021 def.':>14}{'bad':>7}{'def.':>7}")
for split in ("holdout", "out_of_time"):
    g = s[s["split"] == split]
    k = g[g["outcome"] != "indeterminate"]
    print(f"{split:<20}{len(g):>7,}"
          f"{metrics.gini(k['score'], k['bad']):>12.3f}"
          f"{metrics.gini(g['score'], g['d12']):>14.3f}"
          f"{k['bad'].mean():>7.2%}{g['d12'].mean():>7.2%}")
extra = s[(s["d12"] == 1) & (s["outcome"] != "bad")]
share = len(extra) / s["d12"].sum()
bads = s.loc[s["outcome"] == "bad", "score"].mean()
print(f"\nDefaults the bad flag does not count: {len(extra)} "
      f"({share:.1%}); Mark II-R\nmean {extra['score'].mean():.0f} "
      f"against {bads:.0f} for the bads and {s['score'].mean():.0f} "
      "for all")
