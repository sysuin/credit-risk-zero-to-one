# Default, prepayment and loss from Fernhill's own personal loans, by
# Mark II-R score: the inputs a price needs, measured provisionally.
import json
import sys

import numpy as np
import pandas as pd

import fernhill
from ballast import pricing
from ballast.config import ROOT

sys.path.insert(0, str(ROOT / "code" / "12"))
from _book import at_risk, scored  # noqa: E402

con = fernhill.connect()
a = scored(con)
loans = a[a["outcome"].eq("booked")
          & a["app_date"].between("2019-01-01", "2023-12-31")]
d = loans[["account_id", "m2r"]].merge(at_risk(con), on="account_id")
d["band"] = pd.cut(d["m2r"], [0, 560, 570, 580, 590, 600, 610, 999],
                   right=False, labels=["<560", "560-569", "570-579",
                                        "580-589", "590-599", "600-609",
                                        "610+"])
fd = pricing.fit_hazard(d["m2r"], d["dflt"], d["months"])
fp = pricing.fit_hazard(d["m2r"], d["prepaid"], d["months"])
print(f"Personal loans applied for 2019-2023: {len(d):,}, "
      f"{d['dflt'].sum():,} defaults")
print(f"{'Mark II-R':<10}{'loans':>7}{'defaults':>9}{'default':>9}"
      f"{'fitted':>8}{'prepay':>8}{'fitted':>8}")
for b, g in d.groupby("band", observed=True):
    mid, n = g["m2r"].mean(), g["months"].sum()
    print(f"{b:<10}{len(g):>7,}{g['dflt'].sum():>9,}"
          f"{pricing.annual_rate(g['dflt'].sum(), n):>9.2%}"
          f"{float(fd.annual(mid)):>8.2%}"
          f"{pricing.annual_rate(g['prepaid'].sum(), n):>8.1%}"
          f"{float(fp.annual(mid)):>8.1%}")
print("(a year, of loans still open; fitted at the band's average)")
half = np.log(2) / -fd.b
print(f"Default rate halves every {half:.1f} points "
      f"(slope {fd.b:.4f}, s.e. {fd.se_b:.4f})")

g = con.execute("""
    WITH p AS (
        SELECT p.*, min(p.month) FILTER (WHERE p.missed >= 3)
                   OVER (PARTITION BY account_id) AS dm
        FROM performance p WHERE product = 'personal'),
    d AS (
        SELECT account_id, dm,
               max(balance_cents) FILTER (WHERE month = dm) AS ead,
               coalesce(sum(paid_cents) FILTER (WHERE month > dm), 0)
                   AS after
        FROM p WHERE dm < DATE '2023-01-01' GROUP BY 1, 2)
    SELECT count(*), sum(ead), sum(after),
           sum(coalesce(r.rec, 0))
    FROM d LEFT JOIN (SELECT account_id, sum(amount_cents) AS rec
                      FROM recoveries GROUP BY 1) r USING (account_id)
    """).fetchone()
lgd = 1 - (g[2] + g[3]) / g[1]
print(f"\nDefaults 2016-2022 ({g[0]:,}): owed ${g[1] / 100:,.0f}; "
      f"paid after\n  ${g[2] / 100:,.0f}; recovered, net of costs, "
      f"${g[3] / 100:,.0f}")
print(f"Loss given default {lgd:.1%} (undiscounted)")
(ROOT / "code" / "12" / "02_book_rates.json").write_text(json.dumps(
    {"default": [fd.a, fd.b, fd.se_b], "prepay": [fp.a, fp.b, fp.se_b],
     "lgd": round(lgd, 4)}, indent=1) + "\n")
