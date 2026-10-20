# Which characteristics carry protected information: how well each,
# on its own, tells women from men and under-30s from everyone else.
import numpy as np

from ballast import data, fairness
from ballast.config import SEED
from ballast.decision import engine
from ballast.decision import policy as pol

apps = data.load_applications()            # unknowns blanked
apps = apps[apps["product"].astype(str).eq("personal")]
apps = apps.merge(fairness.monitoring(), on="app_id", validate="1:1")
raw = data.load_applications(unknowns=False)
raw = raw.set_index("app_id").loc[apps["app_id"]].reset_index()
card = engine.load_champion(pol.load_policy())
apps["Mark II-R score"] = card.score(engine.prepare(raw)).to_numpy()
apps["Mark I score"] = apps["mark1_score"]
# A control: a six-sided die, which carries nothing by construction.
die = np.random.default_rng(SEED).integers(1, 7, len(apps))
apps["a die (control)"] = die.astype(str)
fm = apps[apps["gender"].isin(["F", "M"])]
woman = fm["gender"].eq("F").astype(int)
young = (apps["age"].astype(int) < 30).astype(int)
COLS = ["a die (control)", "region", "channel", "purpose",
        "employment", "housing",
        "dependants", "enquiries_6m", "revolving_utilisation",
        "bureau_score", "employment_months", "address_months",
        "oldest_account_months", "revolving_balance_cents",
        "amount_requested_cents", "stated_income_cents",
        "Mark I score", "Mark II-R score"]
print(f"{len(apps):,} personal applicants; 0.5 = carries nothing")
print(f"{'characteristic':<26}{'women/men':>11}{'under 30':>10}")
for c in COLS:
    print(f"{c.replace('_cents', ''):<26}"
          f"{fairness.separation(fm[c], woman):>11.3f}"
          f"{fairness.separation(apps[c], young):>10.3f}")
