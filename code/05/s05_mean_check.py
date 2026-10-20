# A drift check: each month's mean bureau score against the mean of
# the six months before; the months it would have stopped the load.
import fernhill

THRESHOLD = 15.0     # points; ordinary months move by a few

con = fernhill.connect()
months = con.execute("""
    SELECT strftime(app_date, '%Y-%m'), avg(bureau_score)
    FROM applications GROUP BY 1 ORDER BY 1
""").fetchall()
moves = []
for i in range(6, len(months)):
    before = sum(m for _, m in months[i - 6:i]) / 6
    moves.append((months[i][0], months[i][1] - before))
biggest = sorted(abs(d) for m, d in moves if not m.startswith("2019"))
print(f"months checked: {len(moves)}")
print(f"largest move outside 2019: {biggest[-1]:.1f} points")
print(f"stopped at a threshold of {THRESHOLD:.0f} points:")
for m, d in moves:
    if abs(d) > THRESHOLD:
        print(f"  {m}  {d:+.1f}")
