# Exercise 2.5: the tiers' break-even with other illustrative inputs.
import json

from ballast.config import ROOT
from ballast.loanmath import break_even_default_rate

saved = json.load(open(ROOT / "code/02/09_break_even.json"))
cof = saved["cof"]
print(f"{'price':>6}{'seen':>7}"
      f"{'LGD 80%, 2.5%':>16}{'LGD 60%, 3.5%':>16}")
for tier in saved["tiers"]:
    rate = tier["rate"]
    seen = tier["seen"]
    old = break_even_default_rate(rate, cof, 2.5, 0.80)
    new = break_even_default_rate(rate, cof, 3.5, 0.60)
    print(f"{rate:>5.1f}%{seen:>6.1f}%"
          f"{old:>8.1f}% ({seen / old:>4.0%})"
          f"{new:>8.1f}% ({seen / new:>4.0%})")
