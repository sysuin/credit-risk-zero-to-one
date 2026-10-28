# Do bank-account fields add anything, for the applicants who share?
import datetime as dt
import json

import numpy as np
import statsmodels.api as sm
from scipy.stats import chi2

import fernhill
from ballast.config import ROOT, SEED
from ballast.scorecard import metrics, points, sample

s = sample.load_sample()
s["mark2"] = points.load_scorecard().score(s)
ob = fernhill.connect().execute("""
    SELECT app_id, channel AS ch, ob_avg_balance_cents,
           ob_overdraft_days, ob_income_volatility,
           ob_returned_payments, ob_betting_share
    FROM applications WHERE product = 'personal'
    ORDER BY app_id""").df()
d = s[s["outcome"] != "indeterminate"].merge(ob, on="app_id")
when = d["app_date"]
asked = (((d["ch"] == "online") & (when >= dt.date(2021, 3, 1)))
         | ((d["ch"] == "branch") & (when >= dt.date(2023, 1, 1))))
# Each loan's group: bank data, asked and refused, or never asked.
d["group"] = "never asked"
d.loc[asked, "group"] = "asked, refused"
d.loc[d["ob_avg_balance_cents"].notna(), "group"] = "consented"

print("out-of-time loans")
print(f"{'':<16}{'loans':>7}{'bads':>6}{'bad rate':>10}"
      f"{'Mark II':>9}{'Gini':>7}")
for g in ("consented", "asked, refused", "never asked"):
    x = d[(d["split"] == "out_of_time") & (d["group"] == g)]
    print(f"{g:<16}{len(x):>7,}{x['bad'].sum():>6}"
          f"{x['bad'].mean():>10.2%}{x['mark2'].mean():>9.1f}"
          f"{metrics.gini(x['mark2'], x['bad']):>7.3f}")

c = d[d["group"] == "consented"].copy()
c["lo"] = (c["mark2"] - points.OFFSET) / points.FACTOR
c["balance"] = np.log(c["ob_avg_balance_cents"] / 100)
c["overdraft"] = np.log1p(c["ob_overdraft_days"])
c["volatility"] = c["ob_income_volatility"]
c["returned"] = c["ob_returned_payments"].clip(upper=3)
c["betting"] = (c["ob_betting_share"] > 0).astype(float)
OB = ["balance", "overdraft", "volatility", "returned", "betting"]
c[["lo"] + OB] = c[["lo"] + OB].astype(float)
early = c["app_date"] < dt.date(2023, 1, 1)
fit, test = c[early], c[~early]
print()
print(f"consenting loans: fitted on 2021-22 ({len(fit):,}, "
      f"{fit['bad'].sum()} bads, online only),")
print(f"  tested on 2023-24 ({len(test):,}, {test['bad'].sum()} bads, "
      f"{(test['ch'] == 'branch').mean():.0%} from branches)")


def logit(cols, frame):
    X = sm.add_constant(frame[cols], has_constant="add")
    return sm.Logit(frame["bad"].to_numpy(), X).fit(disp=0)


def predict(r, cols, frame):
    return r.predict(sm.add_constant(frame[cols], has_constant="add"))


r0, r1 = logit(["lo"], fit), logit(["lo"] + OB, fit)
lr = 2 * (r1.llf - r0.llf)
print(f"  adding the five fields on 2021-22: LR {lr:.1f} on 5 df, "
      f"p {chi2.sf(lr, 5):.3f}")
for name in OB:
    print(f"    {name:<11}{r1.params[name]:>+7.2f}"
          f"  (p {r1.pvalues[name]:.3f})")



def gini_gain(a, b, y):
    """How much better score b ranks the loans than score a."""
    return metrics.gini(b, y) - metrics.gini(a, y)


# Minus the chance of going bad, so that higher means safer, as a
# score does.
p0 = -predict(r0, ["lo"], test)
p1 = -predict(r1, ["lo"] + OB, test)
bad = test["bad"].to_numpy()
rng = np.random.default_rng(SEED)
draws = metrics.bootstrap(gini_gain, p0, p1, bad, n=1000, rng=rng)
ci0 = metrics.interval(metrics.bootstrap(metrics.gini, p0, bad,
                                         n=1000, rng=rng))
ci1 = metrics.interval(metrics.bootstrap(metrics.gini, p1, bad,
                                         n=1000, rng=rng))
g0, g1 = metrics.gini(p0, bad), metrics.gini(p1, bad)
lo, hi = metrics.interval(draws)
print("  Gini on 2023-24:")
print(f"    Mark II alone       {g0:.3f}  "
      f"({ci0[0]:.3f} to {ci0[1]:.3f})")
print(f"    with bank data      {g1:.3f}  "
      f"({ci1[0]:.3f} to {ci1[1]:.3f})")
print(f"    gain               {g1 - g0:+.3f}  "
      f"({lo:+.3f} to {hi:+.3f}),"
      f" {(draws > 0).mean():.1%} above 0")

path = ROOT / "code" / "10" / "09_open_banking.json"
path.write_text(json.dumps({"alone": [g0, *ci0], "with": [g1, *ci1],
                            "gain": [g1 - g0, lo, hi],
                            "bads": int(bad.sum())}, indent=1) + "\n")
