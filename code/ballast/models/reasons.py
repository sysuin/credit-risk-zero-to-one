"""Why an applicant scored as they did: contributions and reasons.

The challenger's trees can say how much each characteristic moved one
applicant's prediction away from the average applicant's. LightGBM
computes it exactly for trees (`pred_contrib`, the TreeSHAP method):
for each row, one number per characteristic plus a `bias` every row
shares, adding up to the row's log odds of going bad. Here they are
turned into points on Mark II's scale, positive meaning safer, so

    score = base + the sum of the characteristics' points

where `base` is the average applicant's score. A contribution is not
yet a reason. Three steps make it closer to one:

- one fact, said once: an applicant with no bureau file is missing
  in nine columns, and their nine contributions are added into one
  reason, `no_file`, as Chapter 8 did for the scorecard;
- only what counted against the applicant (negative points) is a
  candidate, largest first;
- each reason says whether it is something the applicant could
  change (`actionable`), because a reason they cannot act on is a
  different thing to tell them.

`scorecard_reasons` gives Mark II's reasons the way Chapter 8 did:
the lines on which the applicant fell furthest short of the best bin.

    from ballast.models import gbm, reasons
    model = gbm.load()
    reasons.reason_codes(model, frame.iloc[0])
    reasons.scorecard_reasons(points.load_scorecard(), frame.iloc[0])
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ballast.scorecard import points, sample
from ballast.scorecard.model import FILE_FLAG

NO_FILE = "no_file"
# The columns that are missing because the bureau has no file.
BUREAU = [c for c, lab in sample.MISSING_LABEL.items()
          if lab == sample.NO_FILE]
# What each reason says to the applicant, and whether they could act
# on it. Keyed by characteristic, plus the no-file reason.
TEXT = {
    NO_FILE: ("no credit history at the bureau", True),
    "bureau_score": ("credit bureau score", True),
    "enquiries_6m": ("recent applications for credit", True),
    "oldest_account_months": ("length of credit history", False),
    "open_accounts": ("number of open credit accounts", True),
    "revolving_utilisation": ("share of card limits in use", True),
    "revolving_balance": ("balances on cards", True),
    "worst_status_24m": ("recent missed payments", False),
    "public_records": ("court judgments or insolvency", False),
    "dti": ("existing debt payments against income", True),
    "income": ("income", False),
    "amount_requested": ("amount requested", True),
    "term_requested_months": ("term requested", True),
    "age": ("age", False),
    "employment_months": ("time in current employment", False),
    "address_months": ("time at current address", False),
    "dependants": ("number of dependants", False),
    "employment": ("type of employment", False),
    "housing": ("residential status", False),
    "purpose": ("purpose of the loan", True),
    "channel": ("how the application was made", True),
    "region": ("where the applicant lives", False),
}


def in_points(model, frame: pd.DataFrame) -> pd.DataFrame:
    """Contributions on Mark II's scale: one column per
    characteristic (positive = safer) and `base`, the average
    applicant's score. Each row adds up to the challenger's score."""
    c = model.contributions(frame)
    out = -points.FACTOR * c[model.features]
    out["base"] = points.OFFSET - points.FACTOR * c["bias"]
    return out


def grouped(pts: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """The same points with one fact said once: for applicants with
    no bureau file, the bureau columns are added into `no_file`."""
    out = pts.drop(columns="base").copy()
    nofile = frame["bureau_score"].isna().to_numpy()
    cols = [c for c in BUREAU if c in out]
    out[NO_FILE] = np.where(nofile, out[cols].sum(axis=1), 0.0)
    out.loc[nofile, cols] = 0.0
    return out


def _shown(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "missing"
    if isinstance(v, (float, np.floating)):
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
    return str(v)


def reason_codes(model, row: pd.Series, k: int = 4) -> pd.DataFrame:
    """The challenger's reasons for one applicant: the characteristics
    (after grouping) that cost the most points against the average
    applicant, largest first, at most `k`."""
    frame = row.to_frame().T
    g = grouped(in_points(model, frame), frame).iloc[0]
    g = g[g < 0].sort_values(kind="stable").head(k)
    rows = []
    for name, pts in g.items():
        text, act = TEXT[name]
        value = sample.NO_FILE if name == NO_FILE else _shown(row[name])
        rows.append((name, value, round(float(pts), 1), text, act))
    return pd.DataFrame(rows, columns=["characteristic", "value",
                                       "points", "reason",
                                       "actionable"])


def scorecard_reasons(card, row: pd.Series, k: int = 4
                      ) -> pd.DataFrame:
    """Mark II's reasons for one applicant: the lines where they fell
    furthest short of the best bin, largest shortfall first."""
    lines = card.explain(row)
    best = card.table.groupby("characteristic", sort=False)[
        "points"].max()
    lines["short"] = lines["characteristic"].map(best) - lines["points"]
    lines = lines[lines["short"] > 0].sort_values(
        "short", ascending=False, kind="stable").head(k)
    rows = []
    for _, ln in lines.iterrows():
        name = NO_FILE if ln["characteristic"] == FILE_FLAG \
            else ln["characteristic"]
        text, act = TEXT[name]
        rows.append((ln["characteristic"], ln["bin"], int(ln["short"]),
                     text, act))
    return pd.DataFrame(rows, columns=["characteristic", "bin",
                                       "short", "reason",
                                       "actionable"])
