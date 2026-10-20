# The rate rise of 2022-23 reached Fernhill twice: as interest-rate
# risk in loans that kept paying, and as credit risk in borrowers
# whose payments rose.
import json

import fernhill
from ballast import loanmath, pricing
from ballast import securitisation as sec
from ballast.commercial import structure as st
from ballast.config import ROOT

con = fernhill.connect()
mkt = con.execute("SELECT * FROM market_rates WHERE month IN "
                  "(DATE '2021-12-31', DATE '2023-12-31') "
                  "ORDER BY month").df().to_dict("records")
then, now = mkt
book = con.execute("""
    SELECT a.product, p.balance_cents AS bal, p.rate_pct AS rate,
           a.payment_cents AS pay
    FROM performance p JOIN accounts a USING (account_id)
    WHERE p.month = DATE '2021-12-31' AND a.rate_type = 'fixed'
      AND a.product IN ('personal', 'auto', 'mortgage')
      AND p.missed = 0 AND p.balance_cents > 0
      AND NOT p.payment_holiday ORDER BY a.account_id""").df()
book["n"] = sec.remaining_payments(book.bal, book.rate, book.pay)


def value(r, rates):
    """The loan's remaining payments at its rate plus the move in
    Fernhill's funding curve for that many months."""
    shift = (pricing.ftp_pct(now, r.n) - pricing.ftp_pct(then, r.n)
             if rates == "2023" else 0.0)
    return loanmath.present_value([r.pay] * int(r.n), r.rate + shift)


book["v21"] = [value(r, "2021") for r in book.itertuples()]
book["v23"] = [value(r, "2023") for r in book.itertuples()]
print("Fixed-rate loans up to date on 31 Dec 2021: their remaining")
print("payments valued at December 2021's rates and at December")
print("2023's (funding curve +"
      f"{pricing.ftp_pct(now, 24) - pricing.ftp_pct(then, 24):.2f}"
      " points at two years)")
print(f"{'':<10}{'loans':>7}{'years left':>11}{'value $m':>10}"
      f"{'change $m':>11}{'change':>9}")
for prod, g in list(book.groupby("product")) + [("all", book)]:
    chg = g.v23.sum() - g.v21.sum()
    print(f"{prod:<10}{len(g):>7,}{g.n.mean() / 12:>11.1f}"
          f"{g.v21.sum() / 1e8:>10.1f}{chg / 1e8:>11.1f}"
          f"{chg / g.v21.sum():>9.1%}")
cet1 = con.execute("SELECT cet1_cents FROM bank_capital WHERE "
                   "year_end = DATE '2023-12-31'").fetchone()[0]
loss = book.v21.sum() - book.v23.sum()
print(f"fall in value / CET1 at December 2023: {loss / cet1:.1%}")

print("\nThe same rise, through borrowers")
arrears = con.execute("""
    SELECT year(p.month) AS y, a.rate_type,
           avg((p.missed >= 1)::INT) AS behind
    FROM performance p JOIN accounts a USING (account_id)
    WHERE a.product = 'mortgage'
      AND p.status IN ('up_to_date', 'arrears', 'default')
      AND year(p.month) BETWEEN 2021 AND 2025
    GROUP BY ALL ORDER BY ALL""").df()
w = arrears.pivot(index="rate_type", columns="y", values="behind")
rise = dict(con.execute("""
    SELECT a.rate_type, median(p.scheduled_cents / a.payment_cents)
    FROM performance p JOIN accounts a USING (account_id)
    WHERE a.product = 'mortgage' AND p.month = DATE '2023-12-31'
      AND a.open_date <= DATE '2021-12-31' AND p.scheduled_cents > 0
    GROUP BY 1 ORDER BY 1""").fetchall())
print("Mortgages 30+ days behind, average month end, %; and the")
print("median payment in December 2023 over the payment at opening")
print(f"{'':<20}" + "".join(f"{y:>7}" for y in w.columns)
      + f"{'payment':>9}")
for t, row in w.iterrows():
    print(f"{t:<20}" + "".join(f"{v * 100:>7.2f}" for v in row)
          + f"{rise[t]:>8.2f}x")
cov = con.execute("""
    SELECT f.fiscal_year AS fy, f.total_debt_cents AS debt,
           f.ebitda_cents AS ebitda, f.interest_cents AS interest,
           k.cap, k.floor
    FROM financials f JOIN (SELECT company_id,
         min(covenant_max_leverage) AS cap,
         max(covenant_min_interest_cover) AS floor
         FROM facilities GROUP BY 1) k USING (company_id)
    WHERE f.fiscal_year BETWEEN 2019 AND 2024
    ORDER BY f.company_id, f.fiscal_year""").df()
b = st.breaches(cov.debt, cov.ebitda, cov.interest, cov.cap, cov.floor)
cov["cover_breach"] = b["cover_breach"].to_numpy()
cov["lev_breach"] = b["leverage_breach"].to_numpy()
pol = con.execute("SELECT year(month) AS y, policy_rate_pct FROM macro "
                  "WHERE month(month) = 12 ORDER BY 1").df()
pol = dict(zip(pol.y, pol.policy_rate_pct))
print("Commercial clients' accounts below their interest-cover")
print("covenant, and above their leverage covenant, by year")
print(f"{'accounts for':<14}{'clients':>8}{'cover':>8}{'leverage':>10}"
      f"{'policy rate':>13}")
for fy, g in cov.groupby("fy"):
    print(f"{fy:<14}{len(g):>8}{g.cover_breach.mean():>8.0%}"
          f"{g.lev_breach.mean():>10.0%}{pol[fy]:>12.2f}%")
print("policy rate: December of the accounts' year")

by = cov.groupby("fy")
fig = {"fy": [int(y) for y in by.groups],
       "cover_breach": [round(float(x), 4)
                        for x in by.cover_breach.mean()],
       "lev_breach": [round(float(x), 4) for x in by.lev_breach.mean()],
       "policy": [pol[y] for y in by.groups],
       "value": {p: round(float(g.v23.sum() / g.v21.sum() - 1), 4)
                 for p, g in book.groupby("product")}}
(ROOT / "code" / "30" / "07_rates_twice.json").write_text(
    json.dumps(fig) + "\n")
