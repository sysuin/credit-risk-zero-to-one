# Values in the applications table that are not what they look like:
# a zero, a False or a missing value standing for something else.
import fernhill

con = fernhill.connect()
# SQL that labels each application 'asked' or 'never asked'.
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
    # Count the rows meeting the condition, split by a second column.
    split = con.execute(f"""
        SELECT ({by})::VARCHAR AS k, count(*) FROM applications
        WHERE {cond} GROUP BY k ORDER BY count(*) DESC, k
    """).fetchall()
    total = 0
    for _, n in split:
        total += n
    label = "consent" if by == ASKED else by
    # Name the three largest groups, and add "..." if there are more.
    largest = []
    for k, n in split[:3]:
        largest.append(f"{k} {n:,}")
    parts = ", ".join(largest)
    more = ", ..." if len(split) > 3 else ""
    print(f"{cond:<32}{total:>8,}  {means}")
    print(f"    {label}: {parts}{more}")
