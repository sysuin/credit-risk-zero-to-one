# The scale: 600 points is 50 to 1, and 20 points doubles the odds.
import math

from ballast.scorecard import points, sample

print(f"factor = 20 / ln 2          = {points.FACTOR:.4f}")
print(f"offset = 600 - factor ln 50 = {points.OFFSET:.4f}")
print()
print(f"{'score':>6}{'odds':>10}{'bad rate':>10}")
for score in range(520, 701, 20):
    odds = points.odds_at(score)
    print(f"{score:>6}{odds:>8.1f}:1{points.bad_rate_at(score):>10.2%}")
print()
train = sample.load_sample().query("fit")
odds = (len(train) - train["bad"].sum()) / train["bad"].sum()
print(f"training odds {odds:.1f} to 1 sit at "
      f"{points.score_from_log_odds(math.log(odds)):.1f} points")
step = points.odds_at(601) / points.odds_at(600)
print(f"one point multiplies the odds by {step:.4f}")
