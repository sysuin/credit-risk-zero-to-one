# Values in the applications table that are not what they look like:
# a zero, a False or a missing value standing for something else.
import fernhill

con = fernhill.connect()
ASKED = ("CASE WHEN (channel = 'online' AND app_date >= '2021-03-01')"
         " OR (channel = 'branch' AND app_date >= '2023-01-01')"
         " THEN 'asked' ELSE 'never asked' END")
CHECKS = [   # (condition, split the rows by, what the value can mean)
    ("bureau_score IS NULL", "bureau_hit", "no bureau file"),
    ("revolving_utilisation IS NULL", "bureau_hit", "no bureau file"),
    ("oldest_account_months = 0", "bureau_hit", "no bureau file"),
    ("worst_status_24m = 0", "bureau_hit",
     "a clean record, or no file"),
    ("enquiries_6m = 0", "bureau_hit", "no enquiries, or no file"),
    ("employment_months = 0", "employment", "a new job, or no job"),
    ("amount_requested_cents = 0", "product",
     "a card: no amount asked"),
    ("deposit_cents = 0", "product", "no deposit, or none asked"),
    ("collateral_value_cents IS NULL", "product", "nothing secured"),
    ("NOT ob_consent", ASKED, "refused, or never asked"),
]
print(f"{'where':<32}{'rows':>8}  means")
for cond, by, means in CHECKS:
    split = con.execute(f"""
        SELECT ({by})::VARCHAR AS k, count(*) FROM applications
        WHERE {cond} GROUP BY k ORDER BY count(*) DESC, k
    """).fetchall()
    total = sum(n for _, n in split)
    label = "consent" if by == ASKED else by
    parts = ", ".join(f"{k} {n:,}" for k, n in split[:3])
    more = ", ..." if len(split) > 3 else ""
    print(f"{cond:<32}{total:>8,}  {means}")
    print(f"    {label}: {parts}{more}")
