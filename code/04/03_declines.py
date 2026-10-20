# Why Fernhill said no: every decline, by the reason it recorded.
import fernhill

con = fernhill.connect()

# Which check each recorded reason comes from.
STAGE = {"recent_serious_arrears": "policy rule",
         "public_record": "policy rule",
         "thin_file": "policy rule",
         "ltv_over_limit": "policy rule",
         "affordability": "affordability",
         "score_below_cutoff": "score",
         "credit_officer": "override",
         "fraud_check": "fraud check"}

rows = con.execute("""
    SELECT decline_reason, count(*) AS n
    FROM applications WHERE decision = 'decline'
    GROUP BY ALL ORDER BY n DESC, decline_reason
""").fetchall()
declined = sum(n for _, n in rows)
applied = con.execute("SELECT count(*) FROM applications").fetchone()[0]

print(f"{'reason':<24}{'check':<15}{'declines':>9}{'share':>7}")
for reason, n in rows:
    print(f"{reason:<24}{STAGE[reason]:<15}{n:>9,}{n / declined:>7.1%}")
print(f"{'all declines':<39}{declined:>9,}")
print(f"{'as a share of applications':<39}{declined / applied:>16.1%}")
