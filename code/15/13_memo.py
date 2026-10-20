# Meridian's credit memo, rendered for the committee: as text here,
# and as Markdown for the committee pack.
import json

import fernhill
from _meridian import analysis, memo
from ballast.commercial import memo as mm
from ballast.config import ROOT, SANDBOX

con = fernhill.connect()
m = memo(analysis(con))
lines = mm.render(m)
print("\n".join(lines))

out = SANDBOX / "ch15"
out.mkdir(parents=True, exist_ok=True)
(out / "meridian_memo.md").write_text(mm.to_markdown(m))
json.dump(lines, open(ROOT / "code/15/13_memo.json", "w"))
