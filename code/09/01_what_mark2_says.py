# Mark II run over the applicants Fernhill declined for their score.

from ballast.scorecard import points, reject

a = reject.applicants()
card = points.load_scorecard()
a["mark2"] = card.score(a)
a["year"] = [d.year for d in a["app_date"]]
dev = a[a["period"] == "development"]
declined = dev[dev["decline_reason"] == "score_below_cutoff"]
booked = dev[dev["known"] & dev["bad"].notna()]

print("declined for their score, 2016-2022, by year")
print(f"{'year':<6}{'declined':>9}{'Mark II 580+':>14}{'share':>7}"
      f"{'promised':>10}")
for year, g in declined.groupby("year"):
    safe = g[g["mark2"] >= 580]
    print(f"{year:<6}{len(g):>9,}{len(safe):>14,}"
          f"{len(safe) / len(g):>7.1%}"
          f"{points.bad_rate_at(safe['mark2']).mean():>10.2%}")
# The same, for all the development years together
safe = declined[declined["mark2"] >= 580]
print(f"{'all':<6}{len(declined):>9,}{len(safe):>14,}"
      f"{len(safe) / len(declined):>7.1%}"
      f"{points.bad_rate_at(safe['mark2']).mean():>10.2%}")
print()
# Does the promise hold where Fernhill can check it?
booked_safe = booked[booked["mark2"] >= 580]
print(f"booked loans scoring 580+: {len(booked_safe):,}")
print(f"  went bad {booked_safe['bad'].mean():.2%}, Mark II promised "
      f"{points.bad_rate_at(booked_safe['mark2']).mean():.2%}")
print(f"odds at 580 on Mark II's scale: {points.odds_at(580):.1f} to 1")
