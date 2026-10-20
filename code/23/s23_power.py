# Exercise 23.3: how wrong must the PD be before the backtest sees it,
# for one year's personal loans, five years pooled, and the commercial
# book's grade 6?
from ballast import validation as vd

for name, n, pd_ in (("personal, one year", 6_267, 0.0272),
                     ("personal, five years", 5 * 6_267, 0.0272),
                     ("commercial grade 6, eight years", 281, 0.012),
                     ("commercial book, one year", 228, 0.042)):
    print(f"{name:<34}n {n:>6,}  PD {pd_:.2%}  flags "
          f"{vd.detectable(n, pd_):.2f}x")
