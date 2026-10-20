# Two scales in one sample: three ways to handle the bureau's version 3.
import fernhill
import pandas as pd

from ballast import data
from ballast.scorecard import binning, sample, woe

con = fernhill.connect()
apps = data.load_applications(con)
s = sample.build_sample(con, apps)
m = s.attrs["bureau_map"]
print("version 2 score -> version 3, by percentile in 2019:")
print("  " + "  ".join(f"{v}->{m[v]}" for v in (500, 550, 575, 600)))
print("  " + "  ".join(f"{v}->{m[v]}" for v in (650, 700, 750, 800)))

raw = apps.set_index("app_id").loc[s["app_id"], ["bureau_score",
                                                 "bureau_version"]]
s["raw"] = raw["bureau_score"].astype("float64").to_numpy()
s["version"] = raw["bureau_version"].astype(str).to_numpy()
train = s[s["fit"]]
spec = sample.BINNING["bureau_score"]
print()
print(f"{'option':<30}{'loans':>7}{'bads':>6}{'IV':>7}")
for label, d, col in [
        ("raw scores, both versions", train, "raw"),
        ("version 3 loans only",
         train[train["version"] != "v2"], "raw"),
        ("version 2 mapped to 3", train, "bureau_score")]:
    _, bins = binning.bin_characteristic(col, d[col], d["bad"], spec)
    iv = woe.information_value(bins, d[col], d["bad"])
    print(f"{label:<30}{len(d):>7,}{int(d['bad'].sum()):>6}{iv:>7.3f}")

dev = s[(s["split"] != "out_of_time")
        & (s["outcome"] != "indeterminate") & s["raw"].notna()]
print()
print("bad rate by score band, development loans scored on v2 or v3")
print(f"{'band':<10}{'raw v2':>8}{'raw v3':>8}{'ratio':>7}"
      f"{'mapped v2':>11}{'v3':>6}{'ratio':>7}")
cuts = [0, 600, 650, 700, 750, 900]
names = ["<600", "600-649", "650-699", "700-749", "750+"]
rate = {}
for col in ("raw", "bureau_score"):
    band = pd.cut(dev[col], cuts, right=False, labels=names)
    rate[col] = dev.groupby([band, dev["version"]],
                            observed=True)["bad"].mean().unstack()
for b in names:
    r, h = rate["raw"].loc[b], rate["bureau_score"].loc[b]
    print(f"{b:<10}{r['v2']:>8.1%}{r['v3']:>8.1%}"
          f"{r['v3'] / r['v2']:>7.1f}"
          f"{h['v2']:>11.1%}{h['v3']:>6.1%}{h['v3'] / h['v2']:>7.1f}")
era = dev.groupby("version")["bad"].mean()
print(f"{'all':<10}{era['v2']:>8.1%}{era['v3']:>8.1%}"
      f"{era['v3'] / era['v2']:>7.1f}")
