# Fernhill's policy as Ballast writes it down reproduces every
# decision step Fernhill recorded: Mark I's score, the rules, the zones.
import numpy as np
import pandas as pd

from ballast import data
from ballast.decision import policy as pol

raw = data.load_applications(unknowns=False)
apps = raw[raw["product"].astype(str).isin(["personal", "card",
                                             "auto"])]
same = pol.mark1_score(apps) == apps["mark1_score"].astype(int)
print("Mark I recomputed from its points table")
print(f"  {'product':<10}{'applications':>14}{'same score':>12}")
for prod, g in same.groupby(apps["product"].astype(str)):
    print(f"  {prod:<10}{len(g):>14,}{int(g.sum()):>12,}")

limit = pd.Series([pol.period_of(d)[2] for d in apps["app_date"]],
                  index=apps.index)
rule = pol.policy_reason(apps, limit)
rec = apps["decline_reason"].astype(object)
print("\nPolicy rules recomputed against the recorded reason")
print(f"  {'rule':<24}{'fires':>8}{'recorded':>10}{'as fraud':>10}")
for r in pol.RULES:
    fires = rule.eq(r)
    print(f"  {r:<24}{int(fires.sum()):>8,}"
          f"{int((fires & rec.eq(r)).sum()):>10,}"
          f"{int((fires & rec.eq('fraud_check')).sum()):>10,}")
print(f"  {'none, but recorded':<24}"
      f"{int((rule.isna() & rec.isin(pol.RULES)).sum()):>8,}")

p = apps[apps["product"].astype(str).eq("personal")
         & rule.isna() & ~rec.eq("fraud_check")]
margin = p["mark1_score"] - p["cutoff"]
zone = np.select([margin < -pol.REFER, margin < pol.REFER],
                 ["below the band", "refer band"], "above the band")
ok = p["decision"].astype(str).eq("approve")
over = p["override"].astype(object)
print("\nPersonal loans 2016-2025 that passed the rules")
print(f"  {'zone':<16}{'applicants':>11}{'approved':>10}"
      f"{'overrides':>11}")
for z in ("below the band", "refer band", "above the band"):
    m = zone == z
    n_over = int(over[m].notna().sum())
    print(f"  {z:<16}{int(m.sum()):>11,}{ok[m].mean():>10.1%}"
          f"{n_over:>11,}")
