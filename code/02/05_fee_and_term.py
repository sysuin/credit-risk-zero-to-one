# The same broker's fee on the same loan, spread over different terms.
import json

from ballast.config import ROOT
from ballast.loanmath import apr, effective_annual_rate, schedule

AMOUNT = 1_280_000    # PL0023628's amount, in cents
RATE = 9.9            # and its rate, percent a year
FEE = 64_000          # hypothetical, as in the last listing

print(f"effective annual rate at {RATE}%, any term:"
      f" {effective_annual_rate(RATE):.2f}%")
print()
print(f"{'term':>6}{'payment':>10}{'interest':>11}{'APR':>8}")
points = []                      # (term, APR) pairs, for the figure

# Every term from 12 to 60 months, six months apart.
for term in range(12, 61, 6):
    loan = schedule(AMOUNT, RATE, term)
    payment = loan["payment"][0] / 100
    interest = loan["interest"].sum() / 100
    rate = apr(AMOUNT - FEE, loan["payment"].tolist())
    points.append((term, rate))
    # Print whole years only: 12, 24, 36, 48 and 60 months.
    if term % 12 == 0:
        print(f"{term:>6}{payment:>10,.2f}{interest:>11,.2f}"
              f"{rate:>7.2f}%")

json.dump({"rate": RATE, "ear": effective_annual_rate(RATE),
           "points": points},
          open(ROOT / "code/02/05_fee_and_term.json", "w"))
