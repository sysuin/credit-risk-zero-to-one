"""The decision engine: one function takes an application to a decision.

Every personal-loan application goes through the same steps, in the
same order, and the decision records which step decided it:

1. **policy rules** (`policy.policy_reason`): an applicant who breaks
   one is declined, whatever their score, with the rule as the reason;
2. **score**: the champion scorecard's points;
3. **cut-off and refer band** (`Policy.zone`): approve, refer to an
   underwriter, or decline;
4. **amount**: what to lend (`policy.offered_amount`);
5. **reasons**: for a decline or a referral, the lines on which the
   applicant fell furthest short of the best bin, with the absence of
   a bureau file said once.

The engine never reads the truth, never prices (Chapter 12 does) and
never overrides: low-side and high-side overrides stay with people.

    from ballast.decision import engine, policy
    p = policy.load_policy()
    card = engine.load_champion(p)
    raw = data.load_applications(unknowns=False)
    engine.decide(raw.loc[[i]], p, card)      # one application
    engine.decide_all(raw, p, card)           # a frame of them
"""
from __future__ import annotations

from dataclasses import astuple, dataclass, fields

import pandas as pd

from ballast import data
from ballast.decision import policy as pol
from ballast.models.reasons import BUREAU, NO_FILE, TEXT
from ballast.scorecard import points, reject, sample
from ballast.scorecard.model import FILE_FLAG

REASONS = 4                     # reasons given for a decline or refer


@dataclass(frozen=True)
class Decision:
    app_id: str
    decision: str               # approve, refer or decline
    stage: str                  # policy or score
    score: int
    amount_cents: int           # 0 when declined
    reasons: tuple[str, ...]    # characteristics or a rule, in order


def load_champion(p: pol.Policy) -> points.Scorecard:
    """The champion's points table, from where the policy says."""
    folder, name = p.source.split("/")
    if folder == "reject":
        return reject.load_refit(name).scorecard()
    if folder == "mark2":
        return points.load_scorecard()
    raise ValueError(f"unknown champion source {p.source!r}")


def bureau_map() -> pd.Series:
    """Chapter 7's version-2 to version-3 map, as saved."""
    m = pd.read_csv(sample.MARK2 / "bureau_v2_to_v3.csv", index_col=0)
    return m["v3_score"]


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """Characteristics for scoring, from applications as Fernhill
    holds them: unknowns blanked by Chapter 5's rules, then Chapter
    7's characteristics."""
    blank = raw.copy()
    data.apply_unknowns(blank)
    chars = sample.characteristics(blank, bureau_map())
    chars.index = raw.index
    return chars


def shortfalls(card: points.Scorecard,
               chars: pd.DataFrame) -> pd.DataFrame:
    """Points short of each line's best bin, per applicant."""
    pts = card.line_points(chars)
    best = card.table.groupby("characteristic", sort=False)[
        "points"].max()
    return best[pts.columns] - pts


def reasons_for(short: pd.Series, no_file: bool,
                k: int = REASONS) -> tuple[str, ...]:
    """The lines furthest short of their best, largest first. With no
    bureau file, every bureau line's shortfall is one reason."""
    s = short.astype(float).copy()
    if no_file:
        group = [c for c in s.index if c in BUREAU or c == FILE_FLAG]
        s[NO_FILE] = s[group].sum()
        s = s.drop(group)
    s = s[s > 0].sort_values(ascending=False, kind="stable")
    return tuple(NO_FILE if c == FILE_FLAG else c for c in s.index[:k])


def _decide(app_id, rule, score, zone, short, no_file, requested,
            dti, dti_limit) -> Decision:
    """The steps for one application, once its inputs are known."""
    if rule is not None:                              # 1. rules
        return Decision(app_id, "decline", "policy", score, 0, (rule,))
    if zone == "decline":                             # 2-3. score
        return Decision(app_id, "decline", "score", score, 0,
                        reasons_for(short, no_file))
    amount = int(pol.offered_amount([requested], [dti],     # 4.
                                    dti_limit)[0])
    why = reasons_for(short, no_file) if zone == "refer" else ()
    return Decision(app_id, zone, "score", score, amount, why)  # 5.


def decide_all(raw: pd.DataFrame, p: pol.Policy,
               card: points.Scorecard) -> pd.DataFrame:
    """Every application in `raw` through the same steps."""
    if (raw["product"].astype(str) != p.product).any():
        raise ValueError(f"this engine decides {p.product} loans")
    chars = prepare(raw)
    score = card.score(chars).to_numpy()
    zone = p.zone(score)
    short = shortfalls(card, chars)
    rule = pol.policy_reason(raw, p.dti_limit).to_numpy()
    dti = pol.dti_at_decision(raw).to_numpy()
    no_file = chars["bureau_score"].isna().to_numpy()
    req = raw["amount_requested_cents"].astype(float).to_numpy()
    ids = raw["app_id"].astype(str).to_numpy()
    out = [_decide(ids[i], rule[i], int(score[i]), zone[i],
                   short.iloc[i], bool(no_file[i]), req[i], dti[i],
                   p.dti_limit) for i in range(len(raw))]
    cols = [f.name for f in fields(Decision)]
    return pd.DataFrame([astuple(d) for d in out], columns=cols,
                        index=raw.index)


def decide(app: pd.DataFrame, p: pol.Policy,
           card: points.Scorecard) -> Decision:
    """One application (a one-row frame, as `raw.loc[[i]]`)."""
    if len(app) != 1:
        raise ValueError("decide takes one application")
    r = decide_all(app, p, card).iloc[0]
    return Decision(str(r["app_id"]), r["decision"], r["stage"],
                    int(r["score"]), int(r["amount_cents"]),
                    tuple(r["reasons"]))


def reason_text(reasons: tuple[str, ...]) -> list[str]:
    """What each reason says to the applicant."""
    return [TEXT[r][0] if r in TEXT else r.replace("_", " ")
            for r in reasons]


def actionable(reason: str) -> bool:
    return bool(TEXT[reason][1]) if reason in TEXT else False
