# The loan book through ballast.data: typed, unknowns named, every
# check passed, and the counts set against the source.
from ballast import data
from ballast.config import AS_OF

apps = data.load_applications()
accounts = data.load_accounts()
perf = data.load_performance()
data.check_links(apps, accounts, perf)

for name, df in [("applications", apps), ("accounts", accounts),
                 ("performance", perf)]:
    held = df.attrs["source_rows"]
    print(f"{name:<14}{len(df):>11,} loaded{held:>11,} in the source")
print()
print(apps[["app_date", "stated_income_cents", "bureau_score",
            "worst_status_24m", "ob_consent"]].dtypes.to_string())
print()
print(f"{'rule':<17}{'blanked':>8}  meaning")
for rule in data.UNKNOWNS:
    cells = apps.attrs["unknowns"][rule.name]
    print(f"{rule.name:<17}{cells:>8,}  {rule.meaning}")

print()
clean = (apps["worst_status_24m"] == 0).mean()
print(f"no arrears in 24 months, of those with a file: {clean:.1%}")
consent = apps["ob_consent"].mean()
print(f"consent to open banking, of those asked:       {consent:.1%}")
recent = apps[apps["app_date"] > AS_OF.replace(month=10, day=1)]
print(f"applications since October:                    {len(recent):,}")
