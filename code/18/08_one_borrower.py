# One borrower, two PDs: point in time, which moves with the economy,
# and through the cycle, which holds the economy at its average.
import json
from pathlib import Path

import pandas as pd

import fernhill
from ballast.parameters import pd as pdm

con = fernhill.connect()
loans = pdm.personal_loans(con)
panel = pdm.account_months(con, loans)
known = panel[panel.complete]
model = pdm.fit_pd_model(known[known.month.dt.year <= 2022])
long_run = pdm.long_run_unemployment(con)

rows = con.execute("""
    SELECT p.account_id, p.month, p.missed, a.term_months
    FROM performance p JOIN accounts a USING (account_id)
    WHERE a.product = 'personal' AND a.term_months = 60
      AND a.open_date BETWEEN '2018-01-01' AND '2018-06-30'
    ORDER BY p.account_id, p.month""").df()
rows["month"] = pd.to_datetime(rows.month)
span = rows[rows.month.between("2018-07-01", "2022-12-31")]
clean = span.groupby("account_id").agg(n=("missed", "size"),
                                       worst=("missed", "max"))
ok = clean[(clean.n == 54) & (clean.worst == 0)].index
cand = loans[loans.account_id.isin(ok)].copy()
cand["gap"] = (cand.score - loans.score.median()).abs()
pick = cand.sort_values(["gap", "account_id"]).iloc[0]
print(f"{pick.account_id}: opened {pick.open_month:%B %Y}, 60 months,"
      f" Mark II-R {pick.score},\nnever behind to December 2022")

u = pdm.unemployment(con)
b = span[span.account_id == pick.account_id].copy()
start = pick.open_month
b["score"] = pick.score
b["mob"] = ((b.month.dt.year - start.year) * 12
            + b.month.dt.month - start.month)
b["u_now"] = b.month.map(u)
b["u_ahead"] = b.month.map(pdm.ahead(u))
b["ttc"] = model.pd(b, u_ahead=long_run)
b["pit_flat"] = model.pd(b, u_ahead=b.u_now)
b["pit"] = model.pd(b)
print(f"Through the cycle: unemployment held at {long_run:.2f}%")
print(f"\n{'month':<9}{'u now':>6}{'ahead':>7}{'TTC':>8}"
      f"{'PIT':>8}{'PIT, today':>12}")
for _, r in b[b.month.dt.month.isin([6, 12])].iterrows():
    print(f"{r.month:%b %Y}{r.u_now:>7.2f}{r.u_ahead:>7.2f}"
          f"{r.ttc:>8.2%}{r.pit:>8.2%}{r.pit_flat:>12.2%}")
print(f"\nRange 2018-2022: TTC {b.ttc.min():.2%}-{b.ttc.max():.2%}, "
      f"PIT {b.pit.min():.2%}-{b.pit.max():.2%}")
Path(__file__).with_suffix(".json").write_text(json.dumps({
    "account": pick.account_id,
    "month": b.month.dt.strftime("%Y-%m").tolist(),
    "u": b.u_now.tolist(), "ttc": b.ttc.tolist(),
    "pit": b.pit.tolist(), "pit_flat": b.pit_flat.tolist()}))
