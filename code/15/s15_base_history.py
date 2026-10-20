# Exercise 15.2: Meridian's borrowing base in each year, on the
# chapter's assumptions, against what it actually borrowed.
import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
print("$m     base  borrowings  short-term  base below borrowings?")
for y in s.columns:
    c = s[y]
    b = st.borrowing_base(c.receivables, c.inventory).base
    binds = "yes" if b < c.total_debt else "no"
    print(f"{y}  {b / 1e8:>6.2f}{c.total_debt / 1e8:>12.2f}"
          f"{c.short_term_debt / 1e8:>12.2f}  {binds}")
