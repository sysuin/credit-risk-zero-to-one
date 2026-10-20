# The same broker's fee on the same loan, spread over different terms.
import json

from ballast.config import ROOT
from ballast.loanmath import apr, effective_annual_rate, schedule

AMOUNT, RATE = 1_280_000, 9.9    # PL0023628's amount and rate
FEE = 64_000                     # hypothetical, as in the last listing

print(f"effective annual rate at {RATE}%, any term:"
      f" {effective_annual_rate(RATE):.2f}%")
print()
print(f"{'term':>6}{'payment':>10}{'interest':>11}{'APR':>8}")
points = []
for term in range(12, 61, 6):
    s = schedule(AMOUNT, RATE, term)
    payments = s["payment"].tolist()
    rate = apr(AMOUNT - FEE, payments)
    points.append((term, rate))
    if term % 12 == 0:
        print(f"{term:>6}{s['payment'][0] / 100:>10,.2f}"
              f"{s['interest'].sum() / 100:>11,.2f}{rate:>7.2f}%")

json.dump({"rate": RATE, "ear": effective_annual_rate(RATE),
           "points": points},
          open(ROOT / "code/02/05_fee_and_term.json", "w"))
