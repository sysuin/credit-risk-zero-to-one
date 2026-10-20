# Reasons for three declined applicants: challenger against Mark II.
import datetime as dt
import json

from ballast import data
from ballast.config import ROOT
from ballast.models import gbm, reasons
from ballast.scorecard import points, sample

import fernhill

s = sample.load_sample()
model = gbm.fit(s)
card = points.load_scorecard()
apps = data.load_applications(fernhill.connect())
d = apps[(apps["product"] == "personal")
         & (apps["outcome"] == "declined")
         & (apps["app_date"] >= dt.date(2024, 1, 1))
         & (apps["app_date"] <= dt.date(2024, 6, 30))]
x = sample.characteristics(d, s.attrs["bureau_map"])
x[["decline_reason", "mark1_score", "cutoff"]] = d[
    ["decline_reason", "mark1_score", "cutoff"]].to_numpy()
x = x.sort_values("app_id").reset_index(drop=True)


def first_with_channel(rows):
    for _, r in rows.iterrows():
        if "channel" in set(reasons.reason_codes(model, r)
                            ["characteristic"]):
            return r


below = x[x["decline_reason"] == "score_below_cutoff"]
picks = {
    "no bureau file": x[x["bureau_score"].isna()].iloc[0],
    "channel among the reasons": first_with_channel(below),
    "five or more enquiries": below[below["enquiries_6m"] >= 5].iloc[0],
}
out = []
for label, r in picks.items():
    frame = r.to_frame().T
    c = model.score(frame).iloc[0]
    m = card.score(frame).iloc[0]
    print(f"{r['app_id']} ({label}): declined "
          f"{r['decline_reason']}")
    print(f"  Mark I {r['mark1_score']} (cut-off {r['cutoff']}), "
          f"Mark II {m}, challenger {c:.0f}")
    gb = reasons.reason_codes(model, r)
    sc = reasons.scorecard_reasons(card, r)
    print(f"  {'challenger':<26}{'points':>6} {'Mark II':<27}"
          f"{'short':>5}")
    for i in range(max(len(gb), len(sc))):
        left = right = ""
        if i < len(gb):
            g = gb.iloc[i]
            left = f"{g['characteristic']} {g['value']}"
            left = f"{left:<26}{g['points']:>+6.1f}"
        if i < len(sc):
            q = sc.iloc[i]
            right = f"{q['characteristic'] + ' ' + q['bin']:<27}" \
                    f"{q['short']:>5}"
        print(f"  {left:<32} {right}")
    out.append({"app_id": r["app_id"], "label": label,
                "mark2": int(m), "challenger": round(float(c)),
                "challenger_reasons": gb.to_dict(orient="records"),
                "mark2_reasons": sc.to_dict(orient="records")})

path = ROOT / "code" / "10" / "11_reason_codes.json"
path.write_text(json.dumps(out, indent=1, default=str) + "\n")
