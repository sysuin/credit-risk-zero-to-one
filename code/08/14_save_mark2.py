# Save Mark II beside its sample and bins, and load it back.
import json

from ballast.config import ROOT
from ballast.scorecard import metrics, model, points, sample, woe

s = sample.load_sample()
binset = woe.load_binset(sample.MARK2 / "bins.json")
train = model.with_file_flag(s[s["fit"]])
design = model.separate_no_file(binset, train, train["bad"])
saved_bins = json.loads((sample.MARK2 / "bins.json").read_text())
# The shortlist: information value 0.02 or more, strongest first.
iv = {n: b["iv"] for n, b in saved_bins.items()}
by_iv = sorted(iv, key=iv.get, reverse=True)
short = [n for n in by_iv if iv[n] >= 0.02]
X = woe.encode(train, {n: design[n] for n in short + ["bureau_file"]})
chosen, steps = model.select(X, model.target(train), short,
                             force=["bureau_file"])
assert chosen == model.CHARACTERISTICS
mark2, bins = model.fit_mark2(s, binset)
card = points.scorecard(mark2.params.to_dict(), bins)

files = [model.save_model(mark2, chosen, bins, steps=steps,
                          force=["bureau_file"])]
files += points.save_scorecard(card)
# The Gini on each sample, for monitoring to compare against.
det = s[s["outcome"] != "indeterminate"]
perf = {}
for split in model.SPLITS:
    d = det[det["split"] == split]
    gini = metrics.gini(card.score(d), d["bad"])
    perf[split] = {"loans": len(d), "gini": round(gini, 6)}
f = sample.MARK2 / "performance.json"
f.write_text(json.dumps(perf, indent=2) + "\n")
files.append(f)
for f in files:
    print(f"wrote {f.relative_to(ROOT)}  ({f.stat().st_size:,} bytes)")

back = points.load_scorecard()
saved = model.load_model()
same = (back.score(s) == card.score(s)).all()
print()
print(f"reloaded: base {back.base}, {len(back.characteristics)} "
      f"characteristics, {len(back.table)} bins")
print(f"every one of {len(s):,} loans scores the same: {same}")
print(f"saved coefficients all positive: "
      f"{all(v > 0 for v in saved['coef'].values())}")
ginis = [f"{k} {v['gini']:.3f}" for k, v in perf.items()]
print("Gini saved: " + ", ".join(ginis))
