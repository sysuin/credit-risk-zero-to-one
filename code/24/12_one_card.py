# One card on 31 December 2024: a good application score, a year of
# statements, and what the behavioural score made of them.
import datetime as dt
import json

import fernhill
from ballast import monitoring as mon
from ballast import performance as perf
from ballast.config import ROOT

con = fernhill.connect()
day = dt.date(2024, 12, 31)
f = mon.behaviour_frame(con, [day], products=("card",))
card = mon.load_behaviour()["card"]
f["score"] = card.score(f)
pick = f[(f.bad == 1) & (f.application_score >= 640)
         & (f.missed_now == 0)].sort_values(["score", "root_id"])
a = pick.iloc[0]
lines = card.line_points(pick.iloc[[0]]).iloc[0]
print(f"{a.root_id}: opened {a.months_on_book} months before, "
      f"Mark I {a.application_score} at application")
h = perf.stitched_history(con, a.root_id)
p = con.execute("""SELECT month, limit_cents, paid_cents,
                   scheduled_cents FROM performance
                   WHERE account_id = ? ORDER BY month""",
                [a.account_id]).df()
h = h.merge(p, on="month")
yr = h[(h.month.astype(str) > "2023-12-31")
       & (h.month.astype(str) <= "2025-12-31")]
print(f"{'statement':<11}{'balance':>9}{'limit':>8}{'used':>6}"
      f"{'minimum':>9}{'paid':>8}{'missed':>7}")
for r in yr.itertuples():
    mark = " <-" if str(r.month)[:10] == str(day) else ""
    print(f"{str(r.month)[:7]:<11}{r.balance_cents / 100:>9,.0f}"
          f"{r.limit_cents / 100:>8,.0f}"
          f"{r.balance_cents / r.limit_cents:>6.0%}"
          f"{r.scheduled_cents / 100:>9,.0f}{r.paid_cents / 100:>8,.0f}"
          f"{r.missed:>7}{mark}")
parts = [f"{k} {v}" for k, v in lines.items()]
print(f"score {a.score} = base {card.base}, " + ", ".join(parts[:2]))
print("  " + ", ".join(parts[2:]))
print(f"promised bad rate {card.bad_rate(pick.iloc[[0]]).iloc[0]:.1%};"
      f" all cards that day {card.bad_rate(f).mean():.1%}")
rows = [{"month": str(r.month)[:7], "balance": r.balance_cents / 100,
         "limit": r.limit_cents / 100, "paid": r.paid_cents / 100,
         "minimum": r.scheduled_cents / 100, "missed": int(r.missed)}
        for r in yr.itertuples()]
(ROOT / "code" / "24" / "12_one_card.json").write_text(json.dumps(
    {"account": a.root_id, "score": int(a.score),
     "application": int(a.application_score),
     "lines": {k: int(v) for k, v in lines.items()},
     "base": card.base, "rows": rows}, indent=1) + "\n")
