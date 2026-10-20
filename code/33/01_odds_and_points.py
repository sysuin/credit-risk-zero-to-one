# Probability, odds, log odds and points; and Bayes' rule in odds form.
import math

from ballast.scorecard import points, sample, woe

print(f"scale: {points.BASE_SCORE} points = odds of {points.BASE_ODDS} "
      f"to 1; {points.PDO} points double the odds")
print(f"{'score':>6}{'odds g:b':>10}{'log odds':>10}{'bad rate':>10}"
      f"{'logistic':>10}")
for score in range(540, 661, 20):
    odds = float(points.odds_at(score))
    log_odds = math.log(odds)
    bad = float(points.bad_rate_at(score))
    logistic = 1 / (1 + math.exp(log_odds))      # back from log odds
    print(f"{score:>6}{odds:>10.1f}{log_odds:>10.3f}{bad:>10.3%}"
          f"{logistic:>10.3%}")

s = sample.load_sample()
train = s[s["fit"]]
n, bads = len(train), int(train["bad"].sum())
prior = (n - bads) / bads
print(f"\ntraining sample: {n:,} loans, {bads} bad, bad rate "
      f"{bads / n:.4f}")
at = float(points.score_from_log_odds(math.log(prior)))
print(f"odds {prior:.2f} to 1, log odds {math.log(prior):.4f}, "
      f"{at:.1f} points")

# Each bin's odds = the sample's odds x the bin's likelihood ratio,
# and the WoE is the log of that ratio.
binset = woe.load_binset(sample.MARK2 / "bins.json")
t = woe.woe_table(binset["bureau_score"], train["bureau_score"],
                  train["bad"])
print(f"{'bureau bin':<12}{'WoE':>8}{'ratio':>8}{'prior x ratio':>15}"
      f"{'bin odds':>10}")
for _, r in t.iterrows():
    print(f"{r['bin']:<12}{r['woe']:>+8.3f}{math.exp(r['woe']):>8.3f}"
          f"{prior * math.exp(r['woe']):>15.2f}"
          f"{r['goods'] / r['bads']:>10.2f}")

# A fraud rule: frauds are 0.4% of applications; the rule flags 30%
# of them and 2% of genuine applicants. What does a flag mean?
p_fraud, hit, false_alarm = 0.004, 0.30, 0.02
ratio = hit / false_alarm
post_odds = p_fraud / (1 - p_fraud) * ratio
print(f"\nfraud: prior {p_fraud:.1%}, likelihood ratio {ratio:.0f}, "
      f"after a flag {post_odds / (1 + post_odds):.1%}")
