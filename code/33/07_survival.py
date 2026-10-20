# Kaplan-Meier and cumulative incidence on loans whose answer is known.
import numpy as np
import pandas as pd

from ballast.config import SEED
from ballast.parameters import pd as pdm

rng = np.random.default_rng(SEED)
LOANS, TERM = 20_000, 36
H_DEFAULT, H_CLOSE = 0.003, 0.020          # monthly hazards

# Live every loan to the end of its term: month and kind of exit.
u = rng.random((LOANS, TERM))
kind = np.select([u < H_DEFAULT, u < H_DEFAULT + H_CLOSE], [1, 2], 0)
exited = kind > 0
first = np.where(exited.any(axis=1), exited.argmax(axis=1) + 1, TERM)
event = kind[np.arange(LOANS), first - 1]
truth = (event == 1).mean()

# A lender sees each loan only for the months since it opened.
seen = rng.integers(1, TERM + 1, LOANS)
t = np.minimum(first, seen)
ev = np.where(first <= seen, event, 0)            # 0: still open
d = pd.DataFrame({"t": t, "event": ev})
table = pdm.life_table(d, TERM)
km = pdm.kaplan_meier(table).iloc[-1]
ci = pdm.cumulative_incidence(table).iloc[-1]

k = np.arange(1, TERM + 1)
ci_formula = (H_DEFAULT * (1 - H_DEFAULT - H_CLOSE) ** (k - 1)).sum()
km_formula = 1 - (1 - H_DEFAULT) ** TERM
print(f"{LOANS:,} loans, {TERM} months; hazards {H_DEFAULT:.1%} "
      f"default, {H_CLOSE:.1%} close")
print(f"{'36-month PD':<36}{'formula':>10}{'estimate':>10}")
print(f"{'share that default before closing':<36}{ci_formula:>10.4f}"
      f"{truth:>10.4f}")
print(f"{'cumulative incidence (censored)':<36}{ci_formula:>10.4f}"
      f"{ci:>10.4f}")
print(f"{'Kaplan-Meier (closure censored)':<36}{km_formula:>10.4f}"
      f"{km:>10.4f}")
print(f"{'defaults seen / loans':<36}{'':>10}{(ev == 1).mean():>10.4f}")
print(f"open at the reporting date: {(ev == 0).mean():.1%} of loans")
print(f"Kaplan-Meier over cumulative incidence: {km / ci:.2f}")
