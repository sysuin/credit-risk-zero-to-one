# How much of their limits borrowers had drawn in the months before
# they defaulted, against the same products in ordinary months.
import json

import fernhill
from ballast.config import ROOT
from ballast.parameters import ead

con = fernhill.connect()
MONTHS = (24, 18, 12, 9, 6, 3, 2, 1, 0)
u = ead.utilisation_before(con, months=MONTHS)
rev = con.execute("""
    WITH d AS (SELECT facility_id, month AS dm FROM facility_months
               WHERE status = 'defaulted')
    SELECT datediff('month', m.month, d.dm) AS before, count(*),
           sum(m.drawn_cents) / sum(m.limit_cents)
    FROM d JOIN facility_months m USING (facility_id)
    JOIN facilities f USING (facility_id)
    WHERE f.kind = 'revolver'
      AND ((m.status = 'performing' AND m.month < d.dm)
           OR (m.status = 'defaulted' AND m.month = d.dm))
    GROUP BY 1 ORDER BY 1 DESC""").fetchall()
rev = {b: (n, x) for b, n, x in rev}
normal = con.execute("""
    SELECT sum(m.drawn_cents) / sum(m.limit_cents)
    FROM facility_months m JOIN facilities f USING (facility_id)
    WHERE f.kind = 'revolver' AND m.status = 'performing'""").fetchone()

tab = u.set_index(["product", "before"])
print(f"{'months':<8}{'cards':>19}{'overdrafts':>21}{'revolvers':>16}")
print(f"{'before':<8}" + f"{'n':>7}{'drawn':>7}{'behind':>7}" * 2
      + f"{'n':>8}{'drawn':>8}")
for k in MONTHS:
    cells = ""
    for p in ("card", "sme_overdraft"):
        r = tab.loc[(p, k)]
        cells += f"{r['n']:>7,.0f}{r['utilisation']:>7.0%}" \
                 f"{r['behind']:>7.0%}"
    n, x = rev.get(k, (0, float("nan")))
    print(f"{k:<8}{cells}{n:>8}{x:>8.0%}")
perf_u = {p: ead.performing_utilisation(con, p)
          for p in ("card", "sme_overdraft")}
print(f"{'up to date':<8}{'':>5}{perf_u['card']:>7.0%}{'':>7}"
      f"{'':>7}{perf_u['sme_overdraft']:>7.0%}{'':>7}{'':>8}"
      f"{normal[0]:>8.0%}")
print("drawn: balances over limits; behind: share with a payment")
print("missed; last line: every up-to-date (performing) month end")

json.dump({"months": MONTHS,
           "card": [tab.loc[("card", k), "utilisation"]
                    for k in MONTHS],
           "overdraft": [tab.loc[("sme_overdraft", k), "utilisation"]
                         for k in MONTHS],
           "revolver": [rev[k][1] for k in MONTHS],
           "normal": {"card": perf_u["card"],
                      "overdraft": perf_u["sme_overdraft"],
                      "revolver": normal[0]}},
          open(ROOT / "code/19/12_utilisation.json", "w"))
