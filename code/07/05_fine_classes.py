# Fine classes of the bureau score: twenty slices of the training loans.
from ballast.scorecard import binning, sample

s = sample.build_sample()
train = s[s["fit"]]
x, bad = train["bureau_score"], train["bad"]
spec = sample.BINNING["bureau_score"]
fine = binning.fine_classes("bureau_score", x, bad,
                            missing=spec["missing"],
                            decimals=spec["decimals"])
c = binning.counts(fine, x, bad)
c["rate"] = c["bads"] / c["n"]
print(f"{'bureau score':<14}{'loans':>7}{'bads':>6}{'bad rate':>10}")
prev, ups = None, 0
for _, r in c.iterrows():
    # Mark a slice that is riskier than the one below it in score.
    wrong = (prev is not None and r["bin"] != fine.missing
             and r["rate"] > prev)
    ups += wrong
    print(f"{r['bin']:<14}{r['n']:>7,}{r['bads']:>6,}{r['rate']:>10.1%}"
          + ("  <- up" if wrong else ""))
    prev = r["rate"]
print(f"steps where the bad rate rises with the score: {ups} of "
      f"{len(c) - 2}")
