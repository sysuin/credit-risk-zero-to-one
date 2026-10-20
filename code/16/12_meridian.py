# Meridian graded: Ballast's model on its 2025 accounts and on the pro
# forma with the facility drawn, the analyst's override, and the loss
# cost the memo was waiting for.
import sys

import pandas as pd

import fernhill
from ballast.commercial import rating as rt
from ballast.commercial import spreading as sp
from ballast.config import ROOT, TODAY

sys.path.append(str(ROOT / "code" / "15"))
import _meridian  # noqa: E402  Chapter 15's helper: the case and memo

con = fernhill.connect()
a = _meridian.analysis(con)
model = rt.load_model()
rows = a["s"].T.loc[[2024, 2025]].copy()
pro = rows.loc[[2025]].copy()
added = int(a["pf"].debt) - int(pro.total_debt.iloc[0])
pro["total_debt"] = int(a["pf"].debt)
pro["interest"] = int(round(a["pf"].interest))
pro["total_assets"] += added       # the new money funds working capital
pro.index = ["PF"]
cases = pd.concat([rows.rename(index=str), pro])
F = rt.features(cases)
r = sp.ratio_frame(cases)
pd_ = model.pd(F)
print(f"{'accounts':<10}{'leverage':>10}{'cover':>8}{'equity':>8}"
      f"{'revenue':>10}{'PD':>8}{'grade':>7}")
for k in cases.index:
    print(f"{k:<10}{r.leverage[k]:>9.2f}x{r.interest_cover[k]:>7.2f}x"
          f"{r.equity_ratio[k]:>8.1%}"
          f"{cases.revenue[k] / 1e8:>9.1f}m{pd_[k]:>8.2%}"
          f"{rt.grade_of(pd_[k]):>7}")
c = model.contributions(F.loc["PF"])
print("pro forma, log odds against the average client:\n  "
      + ", ".join(f"{rt.SHORT[n]} {v:+.2f}" for n, v in c.items()))

pf_grade = int(rt.grade_of(pd_["PF"]))
mr, ms = a["r"], a["s"]
me = sp.company_id(con, "Meridian Supply Co.")
peers = sp.peer_ratios(con, "wholesale", 2024, exclude=[me])
negative = int((ms.loc["free_cash_flow"] < 0).sum())
ov = rt.Override(
    company="Meridian Supply Co. (prospect)",
    review_date=TODAY, model_grade=pf_grade,
    grade=pf_grade + 2,
    reasons=[
        "Receivable days rose from "
        f"{mr.loc['receivable_days', 2022]:.0f} to "
        f"{mr.loc['receivable_days', 2025]:.0f} in three years; "
        "the cause and the customers are not yet known.",
        f"Free cash flow negative in {negative} of {ms.shape[1]} "
        f"years; cash at {mr.loc['cash_days', 2025]:.0f} days of "
        f"costs against a peer median of "
        f"{peers.cash_days.median():.0f}.",
        f"{mr.loc['payout', 2025]:.0%} of 2025's profit paid out "
        "while borrowings rose.",
        "2025 accounts are unaudited, and Meridian has no history "
        "with Fernhill.",
    ],
    by="credit analyst; to the credit committee",
    revisit_when="audited 2025 accounts and twelve monthly aged "
                 "receivables listings, or any covenant breach.")
print()
print("\n".join(ov.lines()))

book = _meridian.book_loss_cost(con, a["limit"])
lgd, drawn = book["loss"], book["drawn"]
print(f"\nloss cost on ${a['limit'] / 1e8:.0f}m at {lgd:.0%} loss "
      f"and {drawn:.0%} drawn at default")
for label, p in (("book average (Chapter 15)", book["pd"]),
                 (f"model grade {pf_grade}", rt.pd_of(pf_grade)),
                 (f"assigned grade {ov.grade}", ov.pd)):
    cost = p * lgd * drawn * a["limit"] / 100
    print(f"  {label:<27}PD {p:>6.2%}  ${cost:>9,.0f} a year")
lo, hi = (x / 100 for x in a["income"])
cost = ov.pd * lgd * drawn * a["limit"] / 100
print(f"margin and fees ${lo:,.0f} to ${hi:,.0f}: "
      f"{lo / cost:.1f} to {hi / cost:.1f} times the loss cost")
