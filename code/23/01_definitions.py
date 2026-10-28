# The validator's first question: is Mark II-R's bad flag the event
# the PD and the provision count? Every booked loan in Mark II's
# sample, flagged both ways over its first twelve months.

import fernhill
from _cache import loans
from ballast import performance as perf
from ballast.scorecard import metrics, reject, sample

con = fernhill.connect()
# Mark II's sample of booked loans, each scored by Mark II-R
book = sample.load_sample()
book["score"] = reject.load_refit("mark2_retro_ws").scorecard().score(
    book)
# d12: 1 if the loan defaulted (2021 definition) in its first year
book = book.merge(loans(con)[["account_id", "d12"]], on="account_id",
                  validate="1:1")
# What triggered each loan's first 2021-definition default
eps = perf.default_episodes(con, "dod2021", products=["personal"])
first = perf.first_defaults(eps)[["account_id", "trigger"]]
book = book.merge(first, on="account_id", how="left")
bankrupt = book["trigger"] == "bankruptcy"

print(f"{len(book):,} booked loans, applied 2016 to mid-2024")
print(f"{'Mark II-R label':<17}{'loans':>8}{'2021 default in 12m':>21}"
      f"{'by bankruptcy':>15}")
for label in ("good", "indeterminate", "bad"):
    group = book[book["outcome"] == label]
    defaulted = group[group["d12"] == 1]
    by_bk = (defaulted["trigger"] == "bankruptcy").sum()
    print(f"{label:<17}{len(group):>8,}{len(defaulted):>21,}"
          f"{by_bk:>15,}")
all_bk = ((book["d12"] == 1) & bankrupt).sum()
print(f"{'all':<17}{len(book):>8,}{book['d12'].sum():>21,}"
      f"{all_bk:>15,}")

print(f"\n{'Gini of Mark II-R':<20}{'loans':>7}{'on its bad':>12}"
      f"{'on 2021 def.':>14}{'bad':>7}{'def.':>7}")
for split in ("holdout", "out_of_time"):
    group = book[book["split"] == split]
    # The bad flag leaves indeterminate loans out; the 2021 one does not
    known = group[group["outcome"] != "indeterminate"]
    gini_bad = metrics.gini(known["score"], known["bad"])
    gini_def = metrics.gini(group["score"], group["d12"])
    print(f"{split:<20}{len(group):>7,}{gini_bad:>12.3f}"
          f"{gini_def:>14.3f}"
          f"{known['bad'].mean():>7.2%}{group['d12'].mean():>7.2%}")

# Defaults under the 2021 definition that the bad flag misses
extra = book[(book["d12"] == 1) & (book["outcome"] != "bad")]
share = len(extra) / book["d12"].sum()
bads = book.loc[book["outcome"] == "bad", "score"].mean()
print(f"\nDefaults the bad flag does not count: {len(extra)} "
      f"({share:.1%}); Mark II-R\nmean {extra['score'].mean():.0f} "
      f"against {bads:.0f} for the bads and "
      f"{book['score'].mean():.0f} for all")
