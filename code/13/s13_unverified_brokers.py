# Exercise 13.4: broker loans approved on unverified income before July
# 2022, re-tested on the DTI rule with income cut to what verification
# typically found for brokers.
from ballast import data, fraud
from ballast.decision import policy as pol

raw = data.load_applications(unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")
         & raw["channel"].astype(str).eq("broker")
         & (raw["app_date"].astype(str) < "2022-07-01")].copy()
ver = pl["income_verified"].astype(bool)
ratio = fraud.income_ratio(pl[ver]).median()
limit = pl["app_date"].map(lambda d: pol.period_of(d)[2]).astype(float)
ok = pl["decision"].astype(str).eq("approve") & ~ver
cut = pl.copy()
cut["stated_income_cents"] = (pl["stated_income_cents"].astype(float)
                              * ratio)
fails = ok & (pol.dti_at_decision(cut) > limit)
print(f"median verified/stated, broker, verified before Jul 2022: "
      f"{ratio:.3f}")
print(f"unverified broker approvals {ok.sum():,}; fail DTI at that "
      f"income {fails.sum():,} ({fails.sum() / ok.sum():.1%})")
