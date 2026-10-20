# A grade of 300 borrowers with a 1% PD: what each default count says.
import math

from ballast import monitoring, validation

N, PD = 300, 0.01
print(f"{N} borrowers, PD {PD:.0%}, so {N * PD:.0f} defaults expected")
print(f"{'d':>3}{'binomial p':>12}{'Jeffreys p':>12}{'light':>7}"
      f"{'exact 95%':>17}{'Jeffreys 95%':>17}")
for d in range(0, 9):
    lo, hi = monitoring.binomial_interval(d, N)
    jl, jh = validation.jeffreys_interval(N, d)
    print(f"{d:>3}{validation.binomial_p(N, d, PD):>12.3f}"
          f"{validation.jeffreys_p(N, d, PD):>12.3f}"
          f"{validation.traffic_light(N, d, PD):>7}"
          f"{f'{lo:.2%}-{hi:.2%}':>17}{f'{jl:.2%}-{jh:.2%}':>17}")

# With no defaults at all, how high could the rate be? (rule of three)
lo, hi = monitoring.binomial_interval(0, N, level=0.90)
print(f"\nzero defaults: exact one-sided 95% bound {hi:.2%}; "
      f"3/n = {3 / N:.2%}")
print(f"seen 80% of the time by the amber test: a true rate "
      f"{validation.detectable(N, PD):.1f}x the PD")
print(f"normal approximation to the count: mean {N * PD:.1f}, "
      f"sd {math.sqrt(N * PD * (1 - PD)):.2f}")
