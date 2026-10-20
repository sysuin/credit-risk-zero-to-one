# A truer decline reason: who actually said no to a scored application.
import fernhill

con = fernhill.connect()
rows = con.execute("""
    SELECT CASE
             WHEN decline_reason <> 'score_below_cutoff'
               THEN decline_reason
             WHEN mark1_score < cutoff - 10 THEN 'score_below_refer'
             ELSE 'underwriter_in_refer_band' END AS reason,
           count(*) AS n
    FROM applications WHERE decision = 'decline'
    GROUP BY reason ORDER BY n DESC, reason
""").fetchall()
for reason, n in rows:
    print(f"{reason:<28}{n:>8,}")
