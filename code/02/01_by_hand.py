# PL0000001 repaid month by month: interest first, then the balance.
amount = 15100.00     # dollars lent on 8 January 2016
rate = 10.9           # percent a year
term = 60             # months
payment = 327.56      # what Fernhill asked for each month

monthly_rate = rate / 100 / 12
print(f"monthly rate: {monthly_rate:.6f}")

balance = amount
for month in range(1, term + 1):
    interest = balance * monthly_rate
    balance = balance + interest - payment
    if month in (1, 2, 3, 12, 24, 36, 48, 58, 59, 60):
        print(f"month {month:>2}  interest {interest:>7.2f}"
              f"  balance {balance:>10.2f}")
