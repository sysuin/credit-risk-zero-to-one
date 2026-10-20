# How Fernhill's personal loans of 2016-2018 ended, and what early
# repayment did to the interest they earned.
import fernhill
from ballast.loanmath import apr, effective_interest_rate, schedule

con = fernhill.connect()
loans = con.execute("""
    SELECT a.account_id, year(a.open_date) AS vintage, a.close_reason,
           a.amount_cents, a.rate_pct, a.term_months::INT AS term,
           date_diff('month', a.open_date, a.close_date) AS age,
           sum(p.paid_cents) + arg_max(p.balance_cents, p.month)
               AS received
    FROM accounts a JOIN performance p USING (account_id)
    WHERE a.product = 'personal' AND year(a.open_date) <= 2018
    GROUP BY ALL ORDER BY a.account_id
""").df()

print(f"{'vintage':<9}{'loans':>7}{'prepaid':>9}{'to term':>9}"
      f"{'charged':>9}{'prepaid at':>12}")
for vintage, g in loans.groupby("vintage"):
    reason = g["close_reason"].value_counts()
    pre = g[g["close_reason"] == "prepaid"]
    print(f"{vintage:<9}{len(g):>7,}"
          f"{reason.get('prepaid', 0) / len(g):>9.0%}"
          f"{reason.get('repaid', 0) / len(g):>9.0%}"
          f"{reason.get('charged_off', 0) / len(g):>9.0%}"
          f"{pre['age'].mean():>8.1f} mo")
print(f"average term: {loans['term'].mean():.0f} months")

# Interest the prepaid loans earned, against what their schedules
# promised if every one had run to term.
pre = loans[loans["close_reason"] == "prepaid"]
earned = (pre["received"] - pre["amount_cents"]).sum()
promised = sum(schedule(a, r, t)["interest"].sum()
               for a, r, t in zip(pre["amount_cents"], pre["rate_pct"],
                                  pre["term"]))
print()
print(f"prepaid loans: {len(pre):,}")
print(f"  interest scheduled  ${promised / 100:>14,.0f}")
print(f"  interest earned     ${earned / 100:>14,.0f}"
      f"  ({earned / promised:.0%})")

# The broker loan, repaid in full with its 12th payment.
s = schedule(1_280_000, 9.9, 36)
early = s["payment"].tolist()[:12]
early[-1] += s["closing"][11]           # the payoff, with payment 12
print()
print(f"PL0023628 repaid at month 12: payoff"
      f" ${s['closing'][11] / 100:,.2f}")
her_apr = apr(1_216_000, early)
print(f"  her APR on $12,160 received:      {her_apr:.2f}%")
print(f"  Fernhill's EIR, after commission: "
      f"{effective_interest_rate(1_280_000, early,
                                 costs_paid_cents=25_600):.2f}%")
