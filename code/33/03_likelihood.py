# Maximum likelihood by hand, and the likelihood-ratio test it gives.
import numpy as np
from scipy.stats import chi2

from ballast.scorecard import model, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = s[s["fit"]]
good = model.target(train)
X = woe.encode(train, binset)

# The constant alone: the likelihood is highest at the sample's rate.
p_good = good.mean()
grid = np.linspace(0.95, 0.99, 401)
ll = [good.sum() * np.log(q) + (len(good) - good.sum()) * np.log(1 - q)
      for q in grid]
best = grid[np.argmax(ll)]
print(f"share good {p_good:.4f}; best on a grid {best:.4f}")

small = model.fit(X, good, ["bureau_score"])
large = model.fit(X, good, ["bureau_score", "enquiries_6m"])
lr = 2 * (large.llf - small.llf)
z = large.params["enquiries_6m"] / large.bse["enquiries_6m"]
print(f"log-likelihood, constant only    {small.llnull:>10.2f}")
print(f"log-likelihood, bureau score     {small.llf:>10.2f}")
print(f"log-likelihood, + enquiries      {large.llf:>10.2f}")
print(f"LR statistic {lr:.2f} on 1 df, p = {chi2.sf(lr, 1):.2e}")
print(f"Wald z {z:.2f}, z squared {z * z:.2f}")
print(f"chi-squared on 1 df: {chi2.ppf(0.95, 1):.2f} at 5%, "
      f"{chi2.ppf(0.99, 1):.2f} at 1%, {chi2.ppf(0.90, 1):.2f} for a "
      f"90% interval")
print(f"log loss, + enquiries: {-large.llf / len(good):.4f}")
