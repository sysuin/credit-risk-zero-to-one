# Meridian's covenants: set from its own numbers with the facility
# fully drawn, then the headroom in every year and in the pro forma.
import json

import fernhill
from ballast.commercial import spreading as sp
from ballast.commercial import structure as st
from ballast.config import ROOT

con = fernhill.connect()
m = sp.company_id(con, "Meridian Supply Co.")
s = sp.spread(sp.accounts(con, m))
c = s[2025]
growth = float(sp.ratios(s).loc["revenue_growth", 2025])
limit = int(st.revolver_need(s, 2025, growth=growth).limit)
rate = c.interest / c.total_debt        # 2025's, on every dollar
keep = int(c.long_term_debt)

print(f"pro forma on 2025 EBITDA, interest at {rate:.1%}")
cases = [("$20m on top of all today's debt", 2_000_000_000,
          int(c.total_debt)),
         ("$20m, replacing short-term debt", 2_000_000_000, keep),
         (f"${limit / 1e8:.0f}m, replacing short-term debt", limit,
          keep)]
for label, add, kept in cases:
    pf = st.pro_forma(s, 2025, add=add, keep=kept, rate_new=rate)
    print(f"  {label:<34}{pf.leverage:>6.2f}x{pf.cover:>7.2f}x")
pf = st.pro_forma(s, 2025, add=limit, keep=keep, rate_new=rate)
cap, floor = st.covenant_levels(pf.leverage, pf.cover)
print(f"\ncovenants, {st.HEADROOM:.0%} headroom on the last case:")
print(f"  debt / EBITDA at most {cap:.2f}x; "
      f"EBITDA / interest at least {floor:.2f}x")

t = st.covenant_test(s, cap, floor)
lh, ch = st.ebitda_headroom(pf.leverage, pf.cover, cap, floor)
print(f"\n{'':<16}{'leverage':>10}{'headroom':>10}{'cover':>10}"
      f"{'headroom':>10}")
rows = [(y, t.loc["leverage", y], t.loc["leverage_headroom", y],
         t.loc["cover", y], t.loc["cover_headroom", y])
        for y in s.columns] + [("pro forma", pf.leverage, lh,
                                pf.cover, ch)]
for y, lev, lhr, cov, chr_ in rows:
    print(f"  {y:<14}{lev:>9.2f}x{lhr:>10.0%}{cov:>9.2f}x{chr_:>10.0%}")
low = min(lh, ch)
print(f"\nfully drawn, EBITDA of ${c.ebitda / 1e8:.2f}m could fall to "
      f"${c.ebitda * (1 - low) / 1e8:.2f}m before a breach")
json.dump({"years": list(s.columns),
           "leverage": [float(x) for x in t.loc["leverage"]],
           "cover": [float(x) for x in t.loc["cover"]],
           "pf_leverage": float(pf.leverage),
           "pf_cover": float(pf.cover), "cap": cap, "floor": floor,
           "limit": limit},
          open(ROOT / "code/15/05_meridian_covenants.json", "w"))
