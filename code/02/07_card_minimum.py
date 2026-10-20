# A Fernhill card balance paid off at the minimum, and at a fixed sum.
import json

import fernhill
from ballast.config import ROOT
from ballast.loanmath import revolve

con = fernhill.connect()
balance, rate = con.execute("""
    SELECT median(balance_cents)::BIGINT, median(rate_pct)
    FROM performance
    WHERE product = 'card' AND month = '2025-12-31'
      AND balance_cents > 0
""").fetchone()
print(f"median card balance, December 2025: ${balance / 100:,.2f}")
print(f"median card rate:                   {rate:.2f}%")

# Fernhill's rule: 2.5% of the balance or $25, whichever is greater
# (the whole balance if that is less). Check it against December,
# leaving out cards closed that month: their row shows a balance of
# nothing, with the payoff in what was paid.
due, fits = con.execute("""
    SELECT count(*),
           count(*) FILTER (WHERE abs(scheduled_cents - greatest(
               round(balance_cents * 0.025),
               least(2500, balance_cents))) <= 1)
    FROM performance
    WHERE product = 'card' AND month = '2025-12-31'
      AND scheduled_cents > 0 AND balance_cents > 0
""").fetchone()
print(f"minimums due that fit the rule:     {fits:,} of {due:,}")

# No new spending, and the minimum paid each month.
at_min = revolve(balance, rate)
fixed = revolve(balance, rate, payment_cents=at_min["payment"][0])
print()
print(f"{'':<22}{'at the minimum':>16}{'fixed payment':>16}")
print(f"{'first payment':<22}"
      f"{at_min['payment'][0] / 100:>16,.2f}"
      f"{fixed['payment'][0] / 100:>16,.2f}")
print(f"{'months to clear':<22}{len(at_min):>16}{len(fixed):>16}")
print(f"{'years':<22}{len(at_min) / 12:>16.1f}{len(fixed) / 12:>16.1f}")
print(f"{'interest paid':<22}"
      f"{at_min['interest'].sum() / 100:>16,.2f}"
      f"{fixed['interest'].sum() / 100:>16,.2f}")
floor = at_min[at_min["payment"] == 2500]["month"].min()
print(f"{'minimum hits $25 in':<22}{'month ' + str(floor):>16}")

# What Fernhill's cardholders actually paid in December 2025, among
# those who were up to date, had a minimum to pay and kept the card.
n, exactly, full = con.execute("""
    SELECT count(*),
           count(*) FILTER (WHERE paid_cents = scheduled_cents),
           count(*) FILTER (WHERE paid_cents >= balance_cents)
    FROM performance
    WHERE product = 'card' AND month = '2025-12-31'
      AND scheduled_cents > 0 AND missed = 0 AND balance_cents > 0
""").fetchone()
print()
print(f"cardholders with a minimum due: {n:,}")
print(f"  paid exactly the minimum: {exactly:>6,} ({exactly / n:.1%})")
print(f"  paid the whole balance:   {full:>6,} ({full / n:.1%})")

json.dump({"rate": rate, "balance": balance,
           "fixed_payment": int(at_min["payment"][0]),
           "minimum": at_min["closing"].tolist(),
           "fixed": fixed["closing"].tolist()},
          open(ROOT / "code/02/07_card_minimum.json", "w"))
