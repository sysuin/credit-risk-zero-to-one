# Build Mark II's sample and bins, save them, and load them back.

from ballast.scorecard import sample, woe

s = sample.build_sample()
train = s[s["fit"]]
binset, iv = woe.fit_binset(train, train["bad"], sample.BINNING)
files = sample.save_sample(s)
files.append(woe.save_binset(binset, sample.MARK2 / "bins.json", iv))
for f in files:
    print(f"wrote {f.relative_to(sample.MARK2.parents[2])}")

# What Chapter 8 will do: load both and WoE-code the training loans.
back = sample.load_sample()
bins_back = woe.load_binset(sample.MARK2 / "bins.json")
again = back[back["fit"]]
a = woe.encode(train, binset)
b = woe.encode(again, bins_back)
print()
print(f"sample: {len(back):,} loans, {int(back['bad'].sum())} bads; "
      f"bins for {len(bins_back)} characteristics")
diff = (a.reset_index(drop=True) - b.reset_index(drop=True)).abs()
print(f"largest WoE difference after the round trip: "
      f"{diff.max().max():.1e}")
short = [n for n, v in sorted(iv.items(), key=lambda kv: -kv[1])
         if v >= 0.02]
print(f"shortlist for Chapter 8 ({len(short)}):")
for i in range(0, len(short), 3):
    print("  " + ", ".join(short[i:i + 3]))
