# Four distributions, drawn 200,000 times and checked by formula.
import numpy as np
from scipy.stats import beta, binom, norm

from ballast.config import SEED

rng = np.random.default_rng(SEED)
N = 200_000
print(f"{'quantity':<38}{'formula':>12}{'simulated':>12}")


def show(label, formula, simulated, fmt=".4f"):
    print(f"{label:<38}{formula:>12{fmt}}{simulated:>12{fmt}}")


# Binomial: defaults among 1,000 borrowers who each have a 2% PD.
n, p = 1_000, 0.02
d = rng.binomial(n, p, N)
show("binomial mean defaults", n * p, d.mean(), ".2f")
show("binomial variance", n * p * (1 - p), d.var(), ".2f")
show("P(30 or more defaults)", binom.sf(29, n, p), (d >= 30).mean())

# Normal: the economy's draw in a one-factor model.
z = rng.standard_normal(N)
show("P(Z < -1.96)", norm.cdf(-1.96), (z < -1.96).mean())
show("99.9th percentile of Z", norm.ppf(0.999), np.quantile(z, 0.999))

# Beta: what 3 defaults in 400 say about the rate (Jeffreys).
a, b = 3 + 0.5, 400 - 3 + 0.5
theta = rng.beta(a, b, N)
show("beta mean", a / (a + b), theta.mean())
show("P(rate above 1%)", beta.sf(0.01, a, b), (theta > 0.01).mean())

# Lognormal: assets worth 100 drifting 5% a year, volatility 25%.
mu, sigma, v0 = 0.05, 0.25, 100.0
v1 = v0 * np.exp(mu - sigma**2 / 2 + sigma * rng.standard_normal(N))
show("mean asset value in a year", v0 * np.exp(mu), v1.mean(), ".2f")
show("median asset value", v0 * np.exp(mu - sigma**2 / 2),
     np.median(v1), ".2f")
dd = (np.log(v0 / 70) + mu - sigma**2 / 2) / sigma
show("P(assets below 70)", norm.cdf(-dd), (v1 < 70).mean())
