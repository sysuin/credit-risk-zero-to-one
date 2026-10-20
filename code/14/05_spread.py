# Meridian's four years spread into Ballast's standard lines, with the
# lines the table does not hold derived beside the ones it does.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
print("\n".join(sp.format_spread(s)))

json.dump({str(y): {k: int(v) for k, v in s[y].items()}
           for y in s.columns},
          open(ROOT / "code/14/05_spread.json", "w"))
