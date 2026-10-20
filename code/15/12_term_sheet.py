# The term sheet for Meridian: every number from the earlier listings'
# calls, assembled in _meridian.py beside this file.
import fernhill
from _meridian import analysis, terms
from ballast.commercial import structure as st

con = fernhill.connect()
ts = terms(analysis(con))
print("\n".join(st.format_term_sheet(ts)))
