# Who are the out-of-time loans Mark II scores below 540?
import fernhill
from ballast.scorecard import model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)
d = s[s["outcome"] != "indeterminate"].copy()
d["score"] = card.score(d)
con = fernhill.connect()
apps = con.execute("SELECT app_id, mark1_score, override "
                   "FROM applications WHERE product = 'personal' "
                   "ORDER BY app_id").df()
d = d.merge(apps, on="app_id", how="left")
d["burst"] = d["enquiries_6m"] >= 3
oot = d[d["split"] == "out_of_time"]
low = oot["score"] < 540
print(f"out-of-time below 540: {low.sum()} loans, "
      f"{oot.loc[low, 'bad'].sum()} bads")
print(f"  three or more enquiries: {oot.loc[low, 'burst'].mean():.0%}"
      f" of them, {oot.loc[~low, 'burst'].mean():.1%} of the rest")
n_low = (oot.loc[low, "override"] == "low_side").sum()
print(f"  low-side overrides: {n_low}")
print(f"  Mark I: median {oot.loc[low, 'mark1_score'].median():.0f}, "
      f"lowest {oot.loc[low, 'mark1_score'].min()}")
print()
print(f"{'below 540':<14}{'loans':>7}{'bads':>6}{'bad rate':>10}"
      f"{'implied':>9}")
for split in model.SPLITS:
    x = d[(d["split"] == split) & (d["score"] < 540)]
    print(f"{split:<14}{len(x):>7}{x['bad'].sum():>6}"
          f"{x['bad'].mean():>10.1%}"
          f"{points.bad_rate_at(x['score']).mean():>9.1%}")
