# Exercise 2.3: the broker's fee added to the loan, not taken from it.
from ballast.loanmath import apr, schedule

for label, borrowed, received in [("fee from the advance", 1_280_000,
                                   1_216_000),
                                  ("fee added to the loan", 1_344_000,
                                   1_280_000)]:
    s = schedule(borrowed, 9.9, 36)
    print(f"{label:<22} payment ${s['payment'][0] / 100:,.2f}"
          f"  APR {apr(received, s['payment'].tolist()):.2f}%")
