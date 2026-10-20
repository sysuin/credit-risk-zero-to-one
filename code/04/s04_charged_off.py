# The first personal loan Fernhill charged off, from form to recovery.
import fernhill
from ballast.lifecycle import print_life

con = fernhill.connect()
app = con.execute("""
    SELECT app_id FROM accounts
    WHERE product = 'personal' AND close_reason = 'charged_off'
    ORDER BY close_date, account_id LIMIT 1
""").fetchone()[0]
print_life(con, app)
