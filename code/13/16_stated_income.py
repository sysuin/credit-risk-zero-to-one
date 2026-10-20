# What verification found: verified income over stated income, personal
# loans, by channel and period, and for the self-employed.
from ballast import data, fraud

raw = data.load_applications(unknowns=False)
pl = raw[raw["product"].astype(str).eq("personal")
         & raw["income_verified"].astype(bool)].copy()
pl["ratio"] = fraud.income_ratio(pl)
late = pl["app_date"].astype(str) >= "2022-07-01"
self_emp = pl["employment"].astype(str).eq("self_employed")


def row(name, x):
    r = x["ratio"]
    print(f"{name:<24}{len(x):>7,}{r.median():>8.3f}"
          f"{(r < 0.995).mean():>8.1%}{(r < 0.9).mean():>8.1%}"
          f"{(r < 0.7).mean():>8.1%}")


print(f"{len(pl):,} verified personal applications")
print(f"{'':<24}{'apps':>7}{'median':>8}{'lower':>8}{'by 10%+':>8}"
      f"{'by 30%+':>8}")
for ch in ("branch", "online", "broker"):
    m = pl["channel"].astype(str).eq(ch)
    row(f"{ch}, to Jun 2022", pl[m & ~late])
    row(f"{ch}, from Jul 2022", pl[m & late])
bo = pl["channel"].astype(str).isin(["branch", "online"])
row("branch+online, employed", pl[bo & ~self_emp
                                  & pl["employment"].astype(str)
                                  .eq("employed")])
row("branch+online, self-emp.", pl[bo & self_emp])
