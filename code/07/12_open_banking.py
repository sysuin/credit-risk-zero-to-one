# How many of Mark II's loans have bank-account data, and which ones.
import fernhill

from ballast import data
from ballast.scorecard import sample

con = fernhill.connect()
apps = data.load_applications(con)
s = sample.build_sample(con, apps)
ob = apps.set_index("app_id").loc[s["app_id"]]
s["has_ob"] = ob["ob_avg_balance_cents"].notna().to_numpy()
s["channel_"] = ob["channel"].astype(str).to_numpy()

print(f"{'split':<12}{'loans':>7}{'with bank data':>16}{'share':>7}")
for split, g in s.groupby("split", sort=False):
    print(f"{split:<12}{len(g):>7,}{int(g['has_ob'].sum()):>16,}"
          f"{g['has_ob'].mean():>7.1%}")
train = s[s["fit"]]
print()
print("training loans with bank data, by channel and year:")
t = train[train["has_ob"]]
for (ch, yr), g in t.groupby(
        [t["channel_"], [d.year for d in t["app_date"]]]):
    print(f"  {ch:<8}{yr}{len(g):>6,} loans"
          f"{int(g['bad'].sum()):>4} bads")
