# Exercise 11.4: sizing a randomised test of credit line increases on
# cards that pass every check at review.
from ballast.decision import strategy

reviews_a_year = 6_539          # eligible reviews in 2025 (listing 13)
granted_share = 0.147           # granted in 2025 (listing 13)
base = 0.0203                   # 90+ within 12 months, granted
print("Hold back the increase from a random half of those who pass")
per_month = reviews_a_year * granted_share / 12
for rise in (1.25, 1.5, 2.0):
    n = strategy.n_per_arm(base, base * rise)
    months = strategy.months_to_run(n, per_month, 0.5)
    print(f"  to detect {base:.2%} against {base * rise:.2%}: {n:,} an "
          f"arm, {months} months")
