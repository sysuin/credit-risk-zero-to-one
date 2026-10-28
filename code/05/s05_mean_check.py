# A drift check: each month's mean bureau score against the mean of
# the six months before; the months it would have stopped the load.
import fernhill

THRESHOLD = 15.0     # points; ordinary months move by a few

con = fernhill.connect()
months = con.execute("""
    SELECT strftime(app_date, '%Y-%m'), avg(bureau_score)
    FROM applications GROUP BY 1 ORDER BY 1
""").fetchall()
# For each month after the sixth: how far its mean moved from the
# average of the six months before it.
moves = []
for i in range(6, len(months)):
    month, mean = months[i]
    six_before = [m for _, m in months[i - 6:i]]
    moves.append((month, mean - sum(six_before) / 6))
# The largest move in any year but 2019, ignoring its direction.
biggest = 0.0
for month, move in moves:
    if not month.startswith("2019"):
        biggest = max(biggest, abs(move))
print(f"months checked: {len(moves)}")
print(f"largest move outside 2019: {biggest:.1f} points")
print(f"stopped at a threshold of {THRESHOLD:.0f} points:")
for month, move in moves:
    if abs(move) > THRESHOLD:
        print(f"  {month}  {move:+.1f}")
