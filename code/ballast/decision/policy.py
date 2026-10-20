"""Fernhill's lending policy, as its credit manual writes it down.

A decision is a score and a great deal of policy around it. This
module holds the policy in one place, as data a person can read:

- the **policy rules** that decline an applicant before any score
  is looked at, in the order Fernhill applies them;
- **Mark I**, the 2015 scorecard, as its points table, so that a
  score can be recomputed and re-scored on a different ruler;
- the **cut-off history** of Mark I for personal loans, the product
  offsets and the refer band;
- the rules for **how much** to lend: the personal-loan amount,
  the card limit, the credit line increase;
- `Policy`, the settings Ballast's own engine decides with.

    from ballast.decision import policy
    raw = data.load_applications(unknowns=False)
    policy.mark1_score(raw)            # Fernhill's recorded scores
    policy.policy_reason(raw)          # None, or the rule that fired
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ballast.config import BALLAST

DECISION = BALLAST / "decision"

# ------------------------------------------------- the cut-off history

# Mark I cut-offs for personal loans, with the debt-to-income limit
# that went with each: (in force from, cut-off, DTI limit).
CUTOFFS = [
    (dt.date(2016, 1, 1), 560, 0.50),
    (dt.date(2019, 1, 1), 575, 0.50),
    (dt.date(2020, 4, 1), 610, 0.45),    # the shock
    (dt.date(2021, 2, 1), 525, 0.55),    # the growth push
    (dt.date(2022, 7, 1), 580, 0.50),
]
PRODUCT_OFFSET = {"personal": 0, "card": 5, "auto": -15,
                  "mortgage": -5}
REFER = 10            # the refer band: cut-off - 10 to cut-off + 9
# The growth push: refer-band personal loans and cards approved unseen.
PUSH = (dt.date(2021, 2, 1), dt.date(2022, 6, 30))
# The rate at which a new loan's instalment is worked out for the
# debt-to-income ratio, before any price is known.
ASSESSMENT_RATE = {"personal": 10.9, "auto": 7.9, "card": None}


def period_of(day: dt.date) -> tuple[dt.date, int, float]:
    """The (from, cut-off, DTI limit) in force on a day."""
    current = None
    for row in CUTOFFS:
        if day >= row[0]:
            current = row
    if current is None:
        raise ValueError(f"no policy before {CUTOFFS[0][0]}")
    return current


def cutoff_on(day: dt.date, product: str = "personal") -> int:
    return period_of(day)[1] + PRODUCT_OFFSET[product]


# ------------------------------------------------------ the rules

# In the order Fernhill applies them; the first that fires is the
# reason recorded.
RULES = ("recent_serious_arrears", "public_record", "thin_file",
         "affordability")


def instalment(amount_cents, term, rate_pct):
    """Level monthly payment on what was asked for, in cents."""
    r = rate_pct / 1200
    t = np.asarray(term, dtype=float)
    amount = np.asarray(amount_cents, dtype=float)
    return amount * r / (1 - (1 + r) ** -t)


def dti_at_decision(apps: pd.DataFrame) -> pd.Series:
    """Fernhill's affordability ratio: other debt payments plus the
    new instalment at the assessment rate, over stated monthly
    income. Cards add no instalment."""
    new = np.zeros(len(apps))
    for product, rate in ASSESSMENT_RATE.items():
        m = (apps["product"].astype(str) == product).to_numpy()
        if rate is not None and m.any():
            new[m] = instalment(apps.loc[m, "amount_requested_cents"],
                                apps.loc[m, "term_requested_months"],
                                rate)
    other = apps["other_payments_cents"].astype(float).to_numpy()
    income = apps["stated_income_cents"].astype(float).to_numpy() / 12
    return pd.Series((other + new) / np.maximum(income, 1),
                     index=apps.index, name="dti")


def policy_reason(apps: pd.DataFrame,
                  dti_limit: float | pd.Series = 0.50) -> pd.Series:
    """The first rule each applicant breaks, or None."""
    def flag(x):
        x = pd.Series(x, index=apps.index)
        return x.fillna(False).astype(bool)

    ws = apps["worst_status_24m"].astype(float)
    pr = apps["public_records"].astype(float)
    hit = apps["bureau_hit"].astype(bool)
    fired = {
        "recent_serious_arrears": flag(ws >= 90),
        "public_record": flag(pr > 0),
        "thin_file": flag(~hit & (apps["age"].astype(float) < 25)),
        "affordability": flag(dti_at_decision(apps) > dti_limit),
    }
    reason = np.select([fired[r].to_numpy() for r in RULES],
                       list(RULES), default=None)   # first rule wins
    return pd.Series(reason, index=apps.index, dtype=object,
                     name="policy_reason")


# ------------------------------------------------- Mark I (2015)

# Each line: the upper edges of its bands (a value below the first
# edge is in the first band) and the points of each band.
MARK1_BASE = 140
MARK1 = {
    "bureau_score": ([520, 560, 600, 640, 680, 720, 760],
                     [0, 22, 41, 58, 74, 90, 104, 116]),
    "revolving_utilisation": ([0.15, 0.40, 0.70, 0.95],
                              [62, 55, 44, 30, 18]),
    "enquiries_6m": ([1, 2, 4], [60, 54, 44, 29]),
    "worst_status_24m": ([30, 60, 90], [58, 38, 22, 6]),
    "dti": ([0.15, 0.25, 0.35, 0.45], [60, 54, 45, 34, 22]),
    "employment_months": ([6, 24, 60], [30, 42, 50, 58]),
    "address_months": ([12, 36, 96], [38, 46, 53, 58]),
    "age": ([25, 35, 50], [36, 44, 50, 54]),
}
MARK1_HOUSING = {"owner": 62, "mortgage": 56, "with_family": 44,
                 "renter": 40}
MARK1_NO_FILE = 38          # bureau score points with no file
MARK1_RETIRED = 52          # employment points for the retired
MARK1_UTIL_NO_FILE = 0.5    # utilisation assumed with no file


def band_points(x, edges, pts) -> np.ndarray:
    """Points for each value: the band below each edge, in order."""
    i = np.searchsorted(edges, np.asarray(x, dtype=float), side="right")
    return np.asarray(pts)[i]


def mark1_lines(apps: pd.DataFrame, bureau_edges=None) -> pd.DataFrame:
    """Mark I's points line by line, from the applications table as
    Fernhill holds it (no-file zeros not blanked). `bureau_edges`
    replaces the bureau line's edges, to score on another ruler."""
    edges, pts = MARK1["bureau_score"]
    edges = edges if bureau_edges is None else bureau_edges
    bs = apps["bureau_score"].astype(float).to_numpy()
    util = apps["revolving_utilisation"].astype(float).to_numpy()
    emp = apps["employment"].astype(str).to_numpy()
    out = pd.DataFrame(index=apps.index)
    out["bureau_score"] = np.where(np.isnan(bs), MARK1_NO_FILE,
                                   band_points(bs, edges, pts))
    out["revolving_utilisation"] = band_points(
        np.where(np.isnan(util), MARK1_UTIL_NO_FILE, util),
        *MARK1["revolving_utilisation"])
    values = {"dti": dti_at_decision(apps)}
    for name in ("enquiries_6m", "worst_status_24m", "dti",
                 "employment_months", "address_months", "age"):
        x = values.get(name, apps[name] if name in apps else None)
        out[name] = band_points(x, *MARK1[name])
    out["employment_months"] = np.where(emp == "retired", MARK1_RETIRED,
                                        out["employment_months"])
    out["housing"] = apps["housing"].astype(str).map(MARK1_HOUSING)
    return out


def mark1_score(apps: pd.DataFrame, bureau_edges=None) -> pd.Series:
    """Mark I's score: the base plus every line's points."""
    bad = ~apps["product"].astype(str).isin(["personal", "card",
                                             "auto"])
    if bad.any():
        raise ValueError("Mark I is reproduced here for personal "
                         "loans, cards and car loans only")
    lines = mark1_lines(apps, bureau_edges)
    return (MARK1_BASE + lines.sum(axis=1)).astype(int).rename(
        "mark1_score")


def mark1_on_v2_ruler(apps: pd.DataFrame,
                      v2_to_v3: pd.Series) -> pd.Series:
    """Mark I as it would have scored had its bureau bands followed
    the bureau to version 3: each edge moved to the version-3 score
    at the same percentile. Version-2 applications are unchanged."""
    edges = [int(v2_to_v3[e]) for e in MARK1["bureau_score"][0]]
    v3 = apps["bureau_version"].astype(str).eq("v3").to_numpy()
    return pd.Series(np.where(v3, mark1_score(apps, edges),
                              mark1_score(apps)),
                     index=apps.index, name="mark1_v2_ruler")


# ------------------------------------------------- how much to lend

def offered_amount(requested_cents, dti, dti_limit=0.50):
    """Personal loans: the amount asked for, or 80% of it (to the
    nearest $100) when the ratio is within a tenth of the limit."""
    req = np.asarray(requested_cents, dtype=float)
    tight = np.asarray(dti, dtype=float) > 0.9 * np.asarray(dti_limit)
    cut = np.round(req * 0.8 / 10_000) * 10_000
    return np.where(tight, cut, req).astype(np.int64)


# Cards: the opening limit is a share of stated income, set by the
# Mark I score, between $500 and $20,000, to the nearest $100.
CARD_LIMIT_SHARE = ([620, 660], [0.07, 0.12, 0.18])
CARD_LIMIT_RANGE = (500, 20_000)


def card_limit(stated_income_cents, mark1) -> np.ndarray:
    share = band_points(mark1, *CARD_LIMIT_SHARE)
    dollars = np.clip(np.asarray(stated_income_cents, float) / 100
                      * share, *CARD_LIMIT_RANGE)
    return (np.round(dollars, -2) * 100).astype(np.int64)


# Credit line increases, reviewed every six months on book: a card
# that is up to date, more than half used and passes the behaviour
# checks may get 25% more, to the nearest $100, up to $30,000.
CLI_EVERY = 6
CLI_STEP = 0.25
CLI_MIN_USE = 0.5
CLI_CAP_CENTS = 3_000_000


def line_increase(limit_cents, balance_cents, missed, months_on_book,
                  checks_passed=True) -> np.ndarray:
    """The limit after a review: up by a quarter (capped) where the
    rule allows it, unchanged otherwise. Limits never fall."""
    limit = np.asarray(limit_cents, dtype=float)
    use = np.asarray(balance_cents, float) / np.maximum(limit, 1)
    mob = np.asarray(months_on_book)
    ok = ((np.asarray(missed) == 0) & (use > CLI_MIN_USE)
          & (mob > 0) & (mob % CLI_EVERY == 0)
          & np.asarray(checks_passed, dtype=bool)
          & (limit < CLI_CAP_CENTS))
    new = np.minimum(np.round(limit * (1 + CLI_STEP), -4),
                     CLI_CAP_CENTS)
    return np.where(ok, np.maximum(new, limit), limit).astype(np.int64)


# ------------------------------------------- Ballast's own policy

@dataclass(frozen=True)
class Policy:
    """What Ballast's engine decides personal loans with."""
    champion: str           # the scorecard, by name
    source: str             # where its points table is kept
    cutoff: int             # approve at or above (after the band)
    refer_below: int        # refer from cutoff - refer_below ...
    refer_above: int        # ... to cutoff + refer_above - 1
    dti_limit: float = 0.50
    product: str = "personal"

    def zone(self, score) -> np.ndarray:
        """decline, refer or approve, for each score."""
        s = np.asarray(score)
        lo = self.cutoff - self.refer_below
        hi = self.cutoff + self.refer_above
        return np.select([s < lo, s < hi], ["decline", "refer"],
                         "approve")


def save_policy(p: Policy, path: Path = DECISION) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    f = path / "policy.json"
    f.write_text(json.dumps(asdict(p) | {"rules": list(RULES)},
                            indent=2) + "\n")
    return f


def load_policy(path: Path = DECISION) -> Policy:
    d = json.loads((path / "policy.json").read_text())
    d.pop("rules")
    return Policy(**d)
