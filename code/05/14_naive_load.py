# Loading applications the obvious way, and three answers it gets
# wrong without a word of complaint, and one it refuses.
import fernhill
from ballast.config import AS_OF

con = fernhill.connect()
apps = con.execute("SELECT * FROM applications").df()
print(apps[["app_date", "stated_income_cents", "bureau_score",
            "worst_status_24m", "ob_consent"]].dtypes.to_string())

print()
clean = (apps["worst_status_24m"] == 0).mean()
print(f"applicants with no arrears in 24 months:   {clean:.1%}")
consent = apps["ob_consent"].mean()
print(f"applicants who consent to open banking:    {consent:.1%}")
card = apps.loc[apps["product"] == "card", "amount_requested_cents"]
print(f"mean amount a card applicant asked for:    "
      f"${card.mean() / 100:,.0f}")

print()
try:
    recent = apps[apps["app_date"] > AS_OF.replace(month=10, day=1)]
    print(f"applications since October: {len(recent):,}")
except TypeError as err:
    print(f"TypeError: {err}")
