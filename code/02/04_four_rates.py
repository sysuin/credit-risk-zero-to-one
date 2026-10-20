# One broker loan, four honest rates: nominal, effective, APR and EIR.
import fernhill
from ballast.loanmath import (apr, effective_annual_rate,
                              effective_interest_rate, schedule)

ACCOUNT = "PL0023628"
FEE = 64_000          # hypothetical: the broker's fee, from the advance
COMMISSION = 25_600   # hypothetical: Fernhill's commission to broker

con = fernhill.connect()
amount, term, rate, payment, opened, channel = con.execute("""
    SELECT amount_cents, term_months::INT, rate_pct,
           payment_cents::BIGINT, open_date, channel
    FROM accounts WHERE account_id = ?
""", [ACCOUNT]).fetchone()
print(f"{ACCOUNT}, {channel}, opened {opened}")
print(f"  ${amount / 100:,.0f} over {term} months at {rate}%,"
      f" ${payment / 100:,.2f} a month")

# Fernhill's personal-loan prices that month, best tier first.
prices = con.execute("""
    SELECT DISTINCT offered_rate_pct FROM applications
    WHERE product = 'personal' AND decision = 'approve'
      AND app_date BETWEEN '2025-01-01' AND '2025-01-31'
    ORDER BY 1
""").fetchall()
print("  prices quoted in January 2025:",
      ", ".join(f"{r[0]}%" for r in prices))

# What Fernhill's statement for 2025 says: interest charged, and the
# rate that interest is on the balances she owed month by month.
opening, closing, paid, months, owed = con.execute("""
    SELECT arg_min(balance_cents, month), arg_max(balance_cents, month),
           sum(paid_cents), count(*) FILTER (WHERE paid_cents > 0),
           sum(balance_cents) FILTER (WHERE month < '2025-12-31')
    FROM performance WHERE account_id = ?
""", [ACCOUNT]).fetchone()
interest = paid - (opening - closing)
print(f"2025: {months} payments, ${paid / 100:,.2f};"
      f" interest charged ${interest / 100:,.2f}")
print(f"  which is {interest / owed * 12:.2%} a year on what she owed")
print(f"  still owed at the year's end: ${closing / 100:,.2f}")

payments = schedule(amount, rate, term)["payment"].tolist()
received = amount - FEE
rows = [
    ("nominal rate (the advert)", rate),
    ("effective annual rate", effective_annual_rate(rate)),
    (f"APR on ${received / 100:,.0f} received",
     apr(received, payments)),
    ("  the same, nominal convention",
     apr(received, payments, "nominal")),
    ("APR if there were no fee", apr(amount, payments)),
    ("Fernhill's EIR, after commission",
     effective_interest_rate(amount, payments,
                             costs_paid_cents=COMMISSION)),
    ("flat rate: interest / amount / years",
     (sum(payments) - amount) / amount / (term / 12) * 100),
]
print()
for label, value in rows:
    print(f"{label:<36}{value:>8.2f}%")
