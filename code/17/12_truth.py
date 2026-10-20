# Checking Merton against the answer. The simulator knows each
# company's true one-year PD and distance to default; Fernhill never
# can. This is the one listing in the chapter that reads them.
import pandas as pd

import fernhill
from _listed import listed_panel, next_year
from ballast import market as mk

con = fernhill.connect()
truth = fernhill.connect(truth=True).execute("""
    SELECT company_id, month, pd_1y AS true_pd,
           distance_to_default AS true_dd
    FROM corporate_pd ORDER BY 1, 2""").df()
truth["month"] = truth.month.dt.date
p = listed_panel(con).merge(truth, on=["company_id", "month"])
p["pd_cds"] = mk.pd_from_hazard(mk.hazard_from_spread(p.cds))

r = p[["dd", "true_dd"]].corr().iloc[0, 1]
gap = (p.dd - p.true_dd).quantile([0.1, 0.5, 0.9])
print(f"{len(p):,} company-months")
print(f"  correlation of Ballast's DD with the true DD {r:.3f}")
print(f"  Ballast's DD minus the true DD: p10 {gap[0.1]:+.2f}, median "
      f"{gap[0.5]:+.2f}, p90 {gap[0.9]:+.2f}")

edges = [0, 1e-3, 1e-2, 0.05, 0.2, 1]
labels = ["< 0.1%", "0.1-1%", "1-5%", "5-20%", "> 20%"]
p["band"] = pd.cut(p.true_pd, edges, labels=labels)
print(f"\nmedians by true PD{'':<5}{'months':>7}{'true':>8}"
      f"{'Merton':>8}{'ratio':>7}{'CDS':>8}{'ratio':>7}")
for band, x in p.groupby("band", observed=True):
    cds = x[x.pd_cds.notna()]
    ratio = (cds.pd_cds / cds.true_pd).median()
    shown = f"{ratio:>7.2f}" if ratio < 100 else f"{'-':>7}"
    print(f"  {band:<21}{len(x):>7}{x.true_pd.median():>8.2%}"
          f"{x.pd.median():>8.2%}"
          f"{(x.pd / x.true_pd).median():>7.2f}"
          f"{cds.pd_cds.median():>8.2%}{shown}")

s = next_year(p)
march = s[[m.month == 3 for m in s.month]]
print(f"\nMarch reviews, {len(march)} company-years: "
      f"{march.y.sum()} defaults in the next year")
print(f"  expected on Merton's PD {march.pd.sum():.2f}, on the true "
      f"PD {march.true_pd.sum():.2f}")
