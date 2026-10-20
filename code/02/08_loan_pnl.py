# The broker loan from Fernhill's side: what it earns and what it costs.
import fernhill
from ballast.loanmath import loan_pnl, schedule

AMOUNT, RATE, TERM = 1_280_000, 9.9, 36     # PL0023628
OPEX = 2.5           # illustrative: running costs, % of balance a year
ANNUAL_PD = 1.0 / 100     # illustrative: chance of default in a year
LGD = 0.80                # illustrative: share of the balance lost
COMMISSION = 25_600       # hypothetical, as in 04_four_rates.py

con = fernhill.connect()
cof = con.execute("""
    SELECT cost_of_funds_pct FROM market_rates
    WHERE month = '2025-01-31'
""").fetchone()[0]
print(f"Fernhill's cost of funds, January 2025: {cof:.2f}%")

pnl = loan_pnl(AMOUNT, RATE, TERM, cof, annual_pd=ANNUAL_PD, lgd=LGD,
               opex_pct=OPEX)
balances = schedule(AMOUNT, RATE, TERM)["opening"]
avg = balances.mean()                 # the average balance owed
years = TERM / 12

print()
print(f"{'over 36 months':<24}{'dollars':>11}{'% a year':>10}")
for label, key, sign in [("interest earned", "interest", 1),
                         ("cost of funds", "funding", -1),
                         ("operating cost", "opex", -1),
                         ("expected loss", "expected_loss", -1)]:
    cents = sign * pnl[key]
    print(f"{label:<24}{cents / 100:>11,.2f}"
          f"{cents / avg / years:>10.2%}")
print(f"{'net, before commission':<24}{pnl['net'] / 100:>11,.2f}"
      f"{pnl['net'] / avg / years:>10.2%}")
net = pnl["net"] - COMMISSION
print(f"{'net, after commission':<24}{net / 100:>11,.2f}"
      f"{net / avg / years:>10.2%}")
print()
print(f"average balance owed: ${avg / 100:,.2f}")
print(f"net interest margin: "
      f"{(pnl['interest'] - pnl['funding']) / avg / years:.2%}")
