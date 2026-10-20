# Age: who is approved, by Fernhill and by Ballast, and whether Mark
# II-R's promise held for each age band on the loans that were booked.
import json

from ballast import data, fairness
from ballast.config import ROOT
from ballast.decision import engine
from ballast.decision import policy as pol
from ballast.scorecard import points, reject, sample

raw = data.load_applications(unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")
         & (raw["app_date"].astype(str) >= "2023-01-01")]
p = pol.load_policy()
d = engine.decide_all(pl, p, engine.load_champion(p))
band = fairness.age_band(pl["age"])
fern = pl["decision"].astype(str).eq("approve")
thin = pl["decline_reason"].astype(object).eq("thin_file")
print(f"Personal applicants 2023-2025 ({len(pl):,})")
print(f"{'age':<8}{'appl.':>7}{'Fernhill':>10}{'Ballast':>9}"
      f"{'refer':>7}{'thin file':>11}")
for b in fairness.AGE_LABELS:
    m = (band == b).to_numpy()
    print(f"{b:<8}{m.sum():>7,}{fern[m].mean():>10.1%}"
          f"{(d['decision'][m] == 'approve').mean():>9.1%}"
          f"{(d['decision'][m] == 'refer').mean():>7.1%}"
          f"{thin[m].mean():>11.1%}")
ok = (d["decision"] == "approve").to_numpy()
r = fairness.rates(ok, band.astype(str))["rate"]
print("Ballast's rate over 35-49's: " + ", ".join(
    f"{b} {r[b] / r['35-49']:.2f}" for b in ("18-24", "25-34", "65+")))

s = sample.load_sample()
s = s[s["outcome"].isin(["good", "bad"])].copy()
s["promised"] = points.bad_rate_at(
    reject.load_refit("mark2_retro_ws").scorecard().score(s))
s["bad"] = s["outcome"].eq("bad").astype(int)
s["band"] = fairness.age_band(s["age"]).to_numpy()
print(f"\nBooked loans 2016 to mid-2024 ({len(s):,}), Mark II-R")
print(f"{'age':<8}{'loans':>7}{'bads':>6}{'seen':>8}{'promised':>10}"
      f"{'seen/promised':>15}")
fig = []
for b, x in s.groupby("band", observed=True):
    r = x["bad"].mean() / x["promised"].mean()
    print(f"{b:<8}{len(x):>7,}{x['bad'].sum():>6}"
          f"{x['bad'].mean():>8.2%}"
          f"{x['promised'].mean():>10.2%}{r:>15.2f}")
    fig.append({"band": b, "seen": round(x["bad"].mean(), 5),
                "promised": round(x["promised"].mean(), 5),
                "loans": len(x)})
e = fairness.group_effect(s["promised"], s["bad"], (s["age"] - 40) / 10)
print(f"Each decade of age, once the score is known: {e['coef']:+.3f} "
      f"on\n  the log odds (standard error {e['se']:.3f}, "
      f"p {e['p']:.5f})")
(ROOT / "code" / "13" / "06_age.json").write_text(
    json.dumps(fig, indent=1) + "\n")
