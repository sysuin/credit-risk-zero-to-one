# The seasoning curve, and the economy's push on every borrower.
import numpy as np
import pandas as pd

import fernhill
from fernhill import economy, engine

ages = np.array([1, 3, 6, 9, 12, 14, 18, 24, 36, 48, 60, 120])
lift = engine.seasoning(ages)
print("months on book   log-odds   odds of a first miss")
for a, s in zip(ages, lift):
    print(f"{a:>14}{s:>11.2f}{np.exp(s):>12.2f}x")

macro = fernhill.connect().execute(
    "SELECT month, unemployment_pct FROM macro ORDER BY month").df()
s = economy.stress_factor(macro)
u = macro["unemployment_pct"].to_numpy()
rise = u - np.concatenate([np.full(12, u[0]), u[:-12]])
raw = 0.20 * (u - 4.6) + 0.12 * np.maximum(rise, 0.0)
print()
print(f"{'month':<9}{'unemp.':>7}{'stress':>8}{'without':>9}"
      f"{'personal odds':>15}")
show = ["2016-12", "2019-12", "2020-03", "2020-05", "2020-09",
        "2021-03", "2021-06", "2021-07", "2022-06", "2023-12",
        "2024-06", "2025-12"]
m = pd.to_datetime(macro["month"]).dt.strftime("%Y-%m")
p = engine.PARAMS["personal"]["macro"]
for k in show:
    i = int(np.where(m == k)[0][0])
    print(f"{k:<9}{u[i]:>6.2f}%{s[i]:>8.3f}{raw[i]:>9.3f}"
          f"{np.exp(p * s[i]):>14.2f}x")
i = int(np.argmax(s))
print(f"highest stress: {m[i]}, {s[i]:.3f}")
print(f"without support it would have peaked at {raw.max():.3f}"
      f" ({m[int(np.argmax(raw))]})")
