# The lifecycle map: each step, its table, and how many reached it.
import fernhill
from ballast.lifecycle import STEPS

con = fernhill.connect()

# Consumer applications that reached each step, counted from the rows
# the step left behind.
ACCOUNTS = ("SELECT account_id, app_id FROM accounts"
            " WHERE app_id LIKE 'A%'")
REACHED = {
    "apply": "SELECT count(*) FROM applications",
    "check": """SELECT count(*) FROM applications WHERE decline_reason
                IS NULL OR decline_reason IN ('score_below_cutoff',
                'credit_officer')""",
    "decide": "SELECT count(*) FROM applications"
              " WHERE decision = 'approve'",
    "offer": "SELECT count(*) FROM applications"
             " WHERE outcome = 'booked'",
}
for step in ("book", "service", "events", "collect", "default",
             "close", "recover"):
    table = next(s.table for s in STEPS if s.name == step)
    where = ""
    if step == "close":
        where = ("WHERE t.close_date IS NOT NULL"
                 " AND t.close_reason <> 'migrated'")
    source = "accounts" if step in ("book", "close") else table
    REACHED[step] = f"""
        SELECT count(DISTINCT a.app_id) FROM ({ACCOUNTS}) a
        JOIN {source} t USING (account_id) {where}"""

print(f"{'step':<9}{'table':<16}{'rows':>11}{'applications':>14}")
for s in STEPS:
    rows = con.execute(f"SELECT count(*) FROM {s.table}").fetchone()[0]
    reached = con.execute(REACHED[s.name]).fetchone()[0]
    print(f"{s.name:<9}{s.table:<16}{rows:>11,}{reached:>14,}")
