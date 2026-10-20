# The personal loan book on 31 December 2025: its 12-month PD under
# each of the reporting date's scenarios, and on the master scale.
import pandas as pd

import fernhill
from ballast.commercial import rating as rt
from ballast.config import AS_OF
from ballast.parameters import pd as pdm

con = fernhill.connect()
panel = pdm.account_months(con, pdm.personal_loans(con))
model = pdm.fit_pd_model(panel[panel.complete])
book = panel[panel.month == pd.Timestamp(AS_OF)].copy()
print(f"Performing personal loans on {AS_OF:%d %b %Y}: {len(book):,}"
      f"\nModel fitted on {panel.complete.sum():,} loan-quarters, "
      "2016-2024")

w = con.execute("""SELECT DISTINCT scenario, weight FROM scenarios
                   WHERE as_of = ? ORDER BY scenario""",
                [AS_OF]).df().set_index("scenario").weight
print(f"\n{'scenario':<13}{'weight':>7}{'u 2026':>8}{'PD':>8}"
      f"{'defaults':>10}")
pds = {}
for s in ["upside", "base", "downside", "severe", "stress_2026"]:
    u = pdm.ahead(pdm.unemployment(con, s))[pd.Timestamp(AS_OF)]
    p = model.pd(book, u_ahead=u)
    pds[s] = p
    wt = f"{w[s]:.2f}" if w[s] == w[s] else "-"
    print(f"{s:<13}{wt:>7}{u:>8.2f}{p.mean():>8.2%}{p.sum():>10.1f}")
weighted = sum(w[s] * pds[s] for s in w.index if w[s] == w[s])
print(f"{'weighted':<13}{'':>15}{weighted.mean():>8.2%}"
      f"{weighted.sum():>10.1f}")
lr = pdm.long_run_unemployment(con)
ttc = model.pd(book, u_ahead=lr)
print(f"{'TTC':<13}{'':>7}{lr:>8.2f}{ttc.mean():>8.2%}"
      f"{ttc.sum():>10.1f}")

book["grade"] = pdm.retail_grade(pds["base"], book.missed)
print("\nBase scenario on the master scale (30, 60: loans behind)")
print(f"{'grade':<7}{'loans':>7}{'mean PD':>9}{'lowest':>8}"
      f"{'highest':>9}{'scale PD':>10}")
order = [str(g) for g in rt.GRADES] + ["30", "60"]
for g in [x for x in order if x in set(book.grade)]:
    p = pds["base"][book.grade == g]
    scale = "own" if g in ("30", "60") else f"{rt.pd_of(g):.2%}"
    print(f"{g:<7}{len(p):>7,}{p.mean():>9.2%}{p.min():>8.2%}"
          f"{p.max():>9.2%}{scale:>10}")
