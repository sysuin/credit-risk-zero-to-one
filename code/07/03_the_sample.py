# Mark II's sample: development, holdout and out-of-time, with flags.
import json

from ballast.scorecard import sample

s = sample.build_sample()
t = sample.summary(s)
print(f"{'split':<12}{'loans':>7}{'bads':>6}{'indet.':>8}"
      f"{'bad rate':>10}"
      f"{'holiday':>9}")
for split, r in t.iterrows():
    print(f"{split:<12}{int(r['loans']):>7,}{int(r['bads']):>6,}"
          f"{int(r['indeterminate']):>8,}{r['bad_rate']:>10.2%}"
          f"{int(r['holiday']):>9,}")
print(f"{'fitted to':<12}{int(s['fit'].sum()):>7,}"
      f"{int(s.loc[s['fit'], 'bad'].sum()):>6,}")

dev = s[(s["split"] != "out_of_time")
        & (s["outcome"] != "indeterminate")]
print()
print("development loans with a 2020 payment holiday in their window:")
for flag, g in dev.groupby("holiday"):
    label = "holiday" if flag else "no holiday"
    print(f"  {label:<12}{len(g):>7,} loans{int(g['bad'].sum()):>5,} "
          f"bads  {g['bad'].mean():.2%}")

years = s.assign(year=[d.year for d in s["app_date"]])
by_year = years.groupby("year").agg(loans=("bad", "size"),
                                    bads=("bad", "sum"))
json.dump({"by_year": {int(y): [int(r.loans), int(r.bads)]
                       for y, r in by_year.iterrows()},
           "summary": {k: [int(v["loans"]), int(v["bads"])]
                       for k, v in t.iterrows()}},
          open("code/07/03_the_sample.json", "w"), indent=1)
