# What future payments are worth today, at different discount rates.
import fernhill
from ballast.loanmath import apr, present_value, schedule

con = fernhill.connect()
cof = dict(con.execute("""
    SELECT strftime(month, '%Y-%m'), cost_of_funds_pct
    FROM market_rates WHERE month IN ('2025-01-31', '2025-12-31')
""").fetchall())

# A dollar received later is worth less than a dollar today.
now = cof["2025-12"]          # Fernhill's cost of funds today
print(f"{'$1,000 received in':<20}{f'at {now}%':>10}{'at 9.9%':>10}")
for years in (1, 2, 5, 10):
    flows = [0] * (years * 12 - 1) + [100_000]
    label = f"{years} year" + ("s" if years > 1 else "")
    print(f"{label:<20}{present_value(flows, now) / 100:>10,.2f}"
          f"{present_value(flows, 9.9) / 100:>10,.2f}")

# PL0023628's 36 payments, discounted at three rates.
payments = schedule(1_280_000, 9.9, 36)["payment"].tolist()
her_apr = apr(1_216_000, payments, "nominal")   # 12 x monthly rate
print()
print(f"PL0023628's payments total ${sum(payments) / 100:,.2f}")
for label, rate in [("its own rate", 9.9),
                    ("cost of funds", cof["2025-01"]),
                    ("her APR, nominal", her_apr)]:
    pv = present_value(payments, rate)
    print(f"  worth today at {label:<17}{rate:>6.2f}%"
          f"  ${pv / 100:>10,.2f}")
