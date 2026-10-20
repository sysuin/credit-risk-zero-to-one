# What "no file" does to a ratio built on the bureau's numbers.
import fernhill
from ballast import data
from ballast.scorecard import binning, sample

con = fernhill.connect()
apps = data.load_applications(con)
s = sample.build_sample(con, apps)
pl = apps[apps["product"] == "personal"]
nofile = pl[~pl["bureau_hit"].astype(bool)]
zero = int((nofile["other_payments_cents"] == 0).sum())
print(f"personal applicants with no bureau file: {len(nofile):,}")
print(f"  of whom other payments are exactly $0: {zero:,}")

# The ratio as it would be if the zeros were taken at face value.
train = s[s["fit"]].merge(apps[["app_id", "other_payments_cents",
                                "amount_requested_cents"]], on="app_id")
pay = sample.instalment(train["amount_requested_cents"],
                        train["term_requested_months"])
naive = (train["other_payments_cents"].astype(float) + pay) / (
    train["income"] * 100 / 12)
fine, bins = binning.bin_characteristic(
    "dti", train["dti"], train["bad"], sample.BINNING["dti"])

print()
print("debt-to-income bins on the training loans")
print(f"{'bin':<11}{'own bin: loans':>15}{'bad':>7}"
      f"{'zeros taken: loans':>20}{'bad':>7}")
own = binning.counts(bins, train["dti"], train["bad"])
taken = binning.counts(
    binning.Bins("dti", "numeric", edges=bins.edges), naive,
    train["bad"])
for i, r in own.iterrows():
    line = f"{r['bin']:<11}{r['n']:>15,}{r['bads'] / r['n']:>7.1%}"
    if i < len(taken):
        t = taken.iloc[i]
        line += f"{t['n']:>20,}{t['bads'] / t['n']:>7.1%}"
    print(line)
