# Exercise 9.4: Chapter 8's selection rerun with the retro outcomes.
import textwrap
from dataclasses import replace


from _truth import applicants_with_truth
from ballast.scorecard import metrics, model, reject, sample, woe
from ballast.scorecard.sample import NO_FILE

a = applicants_with_truth()
f = reject.frames(a)
acc, unk = f["accepts"], f["unknown"]
t = reject.training_set("bureau retro", acc, unk,
                        retro_rows=reject.retro())
t = model.with_file_flag(t)
saved = woe.load_binset(sample.MARK2 / "bins.json")
short = [n for n, b in saved.items()
         if woe.information_value(b, acc[n], acc["bad"].astype(int))
         >= 0.02]
tmpl = reject.mark2_bins() | {n: saved[n] for n in short}
bins = {}
for n in short + [model.FILE_FLAG]:
    w = reject.weighted_woe(tmpl[n], t[n], t["bad"], t["weight"])
    if tmpl[n].missing == NO_FILE:
        w[NO_FILE] = 0.0
    bins[n] = replace(tmpl[n], woe=w)
X = woe.encode(t, bins)
good = (1 - t["bad"]).astype(int)
chosen, steps = model.select(X, good, short,
                             force=[model.FILE_FLAG])
for s in steps:
    added = s.added or "(stop)"
    print(f"{added:<24}LR {s.lr:>7.1f}  p {s.p:.3g}"
          + (f"  refused {', '.join(s.wrong_sign)}"
             if s.wrong_sign else ""))
print()
for head, cols in (("Mark II has:", model.CHARACTERISTICS[1:]),
                   ("retro chooses:", chosen[1:])):
    print(textwrap.fill(", ".join(cols), 66, initial_indent=head + " ",
                        subsequent_indent="  "))
gone = sorted(set(model.CHARACTERISTICS) - set(chosen))
new = sorted(set(chosen) - set(model.CHARACTERISTICS))
print(f"left out: {', '.join(gone)}; added: {', '.join(new)}")
print()
for name, cols, fr in (("Mark II", model.CHARACTERISTICS, acc),
                       ("retro selection", chosen, t)):
    r = reject.fit(fr, fr["bad"], fr.get("weight"), tmpl, cols)
    g = [metrics.gini(-r.p_bad(d), d["truth"].astype(int))
         for d in (f["holdout"], f["oot"])]
    print(f"{name:<16} Gini, truth: holdout {g[0]:.3f}, "
          f"OOT {g[1]:.3f}")
