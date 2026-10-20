# What each model asks a validator to read: inputs, rules, numbers.
from ballast.models import gbm
from ballast.scorecard import points, sample

s = sample.load_sample()
model = gbm.fit(s)
card = points.load_scorecard()

edges = sum(len(b.edges) for b in card.binset.values())
bins = len(card.table)
size = gbm.size(model)
used = model.booster.feature_importance("split")
print(f"{'':<34}{'Mark II':>10}{'challenger':>12}")
print(f"{'characteristics read':<34}{len(card.characteristics):>10}"
      f"{len(model.features):>12}")
print(f"{'  ... used at least once':<34}{len(card.characteristics):>10}"
      f"{int((used > 0).sum()):>12}")
print(f"{'rules (bin edges, split rules)':<34}{edges:>10}"
      f"{size['splits']:>12,}")
print(f"{'values (points, leaf values)':<34}{bins + 1:>10}"
      f"{size['leaves']:>12,}")
unused = [f for f, n in zip(model.features, used) if n == 0]
print(f"never split on: {', '.join(unused)}")
top = sorted(zip(used, model.features), reverse=True)[:5]
print()
print("characteristics the challenger splits on most often:")
for n, name in top:
    print(f"  {name:<24}{n:>5} split rules")
