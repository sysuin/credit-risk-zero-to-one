# One real application, as Fernhill's systems hold it, field by field.
import json

import fernhill

con = fernhill.connect()
cur = con.execute("""
    SELECT * FROM applications
    WHERE product = 'personal' AND channel = 'online'
      AND outcome = 'booked' AND ob_consent
      AND app_date >= DATE '2023-03-01'
    ORDER BY app_id
    LIMIT 1
""")
a = dict(zip([d[0] for d in cur.description], cur.fetchone()))
limit = a["revolving_balance_cents"] / a["revolving_utilisation"]


def usd(cents):
    return f"${cents / 100:,.0f}"


print(f"{a['app_id']}  {a['product']} loan, {a['channel']}, "
      f"{a['app_date']}")
print("WHAT THEY TOLD US")
print(f"  asked for        {usd(a['amount_requested_cents'])} over "
      f"{a['term_requested_months']} months, {a['purpose']}")
print(f"  age, region      {a['age']}, {a['region']}")
print(f"  stated income    {usd(a['stated_income_cents'])} a year, "
      f"verified: {a['income_verified']}")
if a["income_verified"]:
    found = usd(a["verified_income_cents"])
    print(f"  verified income  {found} a year")
print(f"  employment       {a['employment']}, "
      f"{a['employment_months']} months")
print(f"  housing          {a['housing']}, "
      f"{a['address_months']} months at address, "
      f"{a['dependants']} dependants")
print(f"WHAT THE BUREAU SAID (score version {a['bureau_version']})")
print(f"  score            {a['bureau_score']}")
print(f"  oldest account   {a['oldest_account_months']} months, "
      f"{a['open_accounts']} accounts open")
print(f"  revolving        {usd(a['revolving_balance_cents'])} used of "
      f"{usd(limit)} ({a['revolving_utilisation']:.0%})")
print(f"  enquiries, 6m    {a['enquiries_6m']}; worst status, 24m: "
      f"{a['worst_status_24m']}; public records: {a['public_records']}")
print(f"  other payments   {usd(a['other_payments_cents'])} a month")
print(f"WHAT THEIR BANK ACCOUNT SAID (consent: {a['ob_consent']})")
print(f"  average balance  {usd(a['ob_avg_balance_cents'])}; overdrawn "
      f"{a['ob_overdraft_days']} days in 12 months")
print(f"  income volatility {a['ob_income_volatility']}; returned "
      f"payments {a['ob_returned_payments']}; betting "
      f"{a['ob_betting_share']:.1%}")
print("WHAT FERNHILL DID")
print(f"  Mark I score {a['mark1_score']} against a cut-off of "
      f"{a['cutoff']}: {a['decision']}")
print(f"  offered {usd(a['offered_amount_cents'])} at "
      f"{a['offered_rate_pct']}% over "
      f"{a['offered_term_months']} months: "
      f"{a['outcome']} as {a['account_id']}")

a["app_date"] = str(a["app_date"])
a["revolving_limit_cents"] = round(limit)
with open("code/05/01_one_application.json", "w") as f:
    json.dump(a, f, indent=1, sort_keys=True)
