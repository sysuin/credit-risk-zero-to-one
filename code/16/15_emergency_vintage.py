# The emergency loans on the default clock (from the first payment
# due, month 13), against ordinary term loans, and split by whether
# SME-1 would have approved them.
import json

import fernhill
from ballast import performance as perf
from ballast.config import ROOT

con = fernhill.connect()
eps = perf.default_episodes(con, "dod2021", products=[
    "sme_emergency", "sme_term"])
mobs = [6, 12, 24, 36, 48]
curves = {}
print("cumulative share in default, months on the default clock")
print(f"{'loans':<22}{'n':>6}" + "".join(f"{'m' + str(k):>8}"
                                        for k in mobs))
for product, cohorts in (("sme_emergency", ["2020", "2021"]),
                         ("sme_term", ["2019", "2020", "2021"])):
    t = perf.vintage_table(con, product, eps, clock="due")
    for c in cohorts:
        row = t.loc[c]
        label = f"{'emergency' if 'em' in product else 'term'} {c}"
        cells = "".join(f"{row[k]:>8.1%}" if row[k] == row[k]
                        else f"{'':>8}" for k in mobs)
        print(f"{label:<22}{int(row.accounts):>6,}{cells}")
        curves[label] = [None if v != v else float(v)
                         for v in row[list(range(61))]]

acc = perf.cohort_accounts(con, "sme_emergency", eps, clock="due")
apps = con.execute("""
    SELECT account_id, sme1_score, app_date FROM sme_applications
    WHERE product = 'sme_emergency' AND outcome = 'booked'""").df()
acc = acc.merge(apps, on="account_id")
acc["passes"] = acc.sme1_score >= 150     # the cut-off at the time
print("\nemergency loans by SME-1 at the cut-off of 150")
print(f"{'':<22}{'n':>6}{'m12':>8}{'m24':>8}{'m36':>8}")
for passes, g in acc.groupby("passes"):
    label = "would have passed" if passes else "would have failed"
    cells = "".join(f"{(g.default_mob <= k).mean():>8.1%}"
                    for k in (12, 24, 36))
    print(f"{label:<22}{len(g):>6,}{cells}")
share = (~acc.passes).mean()
print(f"share SME-1 would have declined: {share:.0%}")
out = ROOT / "code" / "16" / "15_emergency_vintage.json"
out.write_text(json.dumps(curves))
