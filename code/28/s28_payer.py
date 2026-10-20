# Exercise 28.5: the same swap with Fernhill paying fixed instead of
# receiving it.

from ballast import securitisation as sec
from ballast.config import SEED

paths = sec.swap_rate_paths(3.34, 0.69, 60, 10_000, SEED)
for label, rf in (("receives fixed", True), ("pays fixed", False)):
    ee, pfe = sec.exposure_profile(
        sec.swap_values(paths, 3.34, 5, 25_000_000, receive_fixed=rf))
    print(f"Fernhill {label}: peak EE ${ee.max():,.0f} "
          f"(month {int(ee.argmax())}),\n  peak PFE ${pfe.max():,.0f}")
up = paths[:, 24] > 3.34
print(f"paths with rates higher after two years: {up.mean():.1%}")
