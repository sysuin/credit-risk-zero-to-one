# Mark II run over the applicants Fernhill declined for their score.

from ballast.scorecard import points, reject

a = reject.applicants()
card = points.load_scorecard()
a["mark2"] = card.score(a)
a["year"] = a["app_date"].map(lambda d: d.year)
dev = a[a["period"] == "development"]
dec = dev[dev["decline_reason"] == "score_below_cutoff"]
book = dev[dev["known"] & dev["bad"].notna()]

print("declined for their score, 2016-2022, by year")
print(f"{'year':<6}{'declined':>9}{'Mark II 580+':>14}{'share':>7}"
      f"{'promised':>10}")
for year, g in dec.groupby("year"):
    hi = g[g["mark2"] >= 580]
    print(f"{year:<6}{len(g):>9,}{len(hi):>14,}"
          f"{len(hi) / len(g):>7.1%}"
          f"{points.bad_rate_at(hi['mark2']).mean():>10.2%}")
hi = dec[dec["mark2"] >= 580]
print(f"{'all':<6}{len(dec):>9,}{len(hi):>14,}"
      f"{len(hi) / len(dec):>7.1%}"
      f"{points.bad_rate_at(hi['mark2']).mean():>10.2%}")
print()
bk = book[book["mark2"] >= 580]
print(f"booked loans scoring 580+: {len(bk):,}")
print(f"  went bad {bk['bad'].mean():.2%}, Mark II promised "
      f"{points.bad_rate_at(bk['mark2']).mean():.2%}")
print(f"odds at 580 on Mark II's scale: {points.odds_at(580):.1f} to 1")
