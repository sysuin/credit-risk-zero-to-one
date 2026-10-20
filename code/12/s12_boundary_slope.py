# Exercise 12.2: the tier edge at Mark I 600 read as a price experiment.
import numpy as np

lo, hi = 0.13, 0.55          # take-up either side (code/12/10 output)
dear, cheap = 19.5, 14.5     # the prices either side
slope = (np.log(lo / (1 - lo)) - np.log(hi / (1 - hi))) \
    / (dear - cheap)
print(f"Log odds of take-up per point across the edge: {slope:.3f}")
print("From the 2024 test: -0.403 (95% interval -0.562 to -0.244)")
