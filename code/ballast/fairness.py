"""Fair lending: who is approved, whether the score is right for each
group, what carries protected information, and reasons a person can
act on.

Fernhill collects each consumer applicant's gender in a separate table,
`applicant_monitoring`, for monitoring only. This module is the one
place in Ballast that reads it, and nothing it returns is ever passed
to a decision. Age is different: it is on the application, and it is
itself a protected characteristic in many places, so it is measured
here in bands and never used as a score.

The measures:

- **approval rates by group** and the **adverse impact ratio**: one
  group's approval rate over a reference group's;
- **calibration within groups**: at the same score, did each group's
  loans go bad at the rate the score promised? `group_effect` asks it
  of all scores at once, as one extra term in a logistic regression;
- **separation**: how well one characteristic, on its own, tells two
  groups apart (0.5 not at all, 1.0 perfectly), the measure of a
  **proxy**;
- **reasons against the cut-off**: the lines on which an applicant
  fell furthest below the average points of applicants who scored at
  the cut-off, instead of below each line's best bin.

    from ballast import fairness
    g = fairness.monitoring(con)              # app_id, gender
    fairness.rates(approved, group)
    fairness.adverse_impact_ratio(approved, group, "F", "M")
    ref = fairness.cutoff_reference(card, chars, 554)
    fairness.cutoff_reasons(card, chars, ref)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import rankdata

import fernhill
from ballast.decision.engine import REASONS, reasons_for
from ballast.scorecard import points

# What `applicant_monitoring.gender` holds: F, M, X (another gender)
# and U (not given). The comparisons are between F and M; X and U are
# reported, and too few to compare.
GENDERS = ("F", "M", "X", "U")
AGE_EDGES = [25, 35, 50, 65]
AGE_LABELS = ["18-24", "25-34", "35-49", "50-64", "65+"]
REFERENCE_WIDTH = 4         # "at the cut-off": cut-off to cut-off + 3


def monitoring(con=None) -> pd.DataFrame:
    """Gender by application, from the monitoring table: the only
    function in Ballast that reads it."""
    con = con if con is not None else fernhill.connect()
    return con.execute("""SELECT app_id, gender
                          FROM applicant_monitoring
                          ORDER BY app_id""").df()


def age_band(age) -> pd.Series:
    """Age in the five bands every table in Chapter 13 uses."""
    a = pd.Series(np.asarray(age, dtype=float))
    i = np.searchsorted(AGE_EDGES, a.to_numpy(), side="right")
    cat = pd.Categorical(np.asarray(AGE_LABELS)[i],
                         categories=AGE_LABELS, ordered=True)
    return pd.Series(cat, index=getattr(age, "index", None))


# ------------------------------------------------ approval rates

def rates(flag, group) -> pd.DataFrame:
    """Rows, how many were flagged (approved, say) and the rate, by
    group, in the group's own order."""
    t = pd.DataFrame({"g": np.asarray(group),
                      "y": np.asarray(flag, dtype=float)})
    out = t.groupby("g", sort=True, observed=True)["y"].agg(
        n="size", yes="sum", rate="mean")
    out["yes"] = out["yes"].astype(int)
    return out


def adverse_impact_ratio(flag, group, protected: str,
                         reference: str) -> float:
    """The protected group's rate over the reference group's: 1.0 is
    parity, below 1.0 the protected group is approved less often."""
    y = np.asarray(flag, dtype=float)
    g = np.asarray(group)
    return float(y[g == protected].mean() / y[g == reference].mean())


def air_interval(flag, group, protected: str, reference: str,
                 rng: np.random.Generator, n: int = 1000,
                 level: float = 0.95) -> tuple[float, float]:
    """A bootstrap interval for the ratio, resampling applicants."""
    y = np.asarray(flag, dtype=float)
    g = np.asarray(group)
    keep = (g == protected) | (g == reference)
    y, p = y[keep], (g[keep] == protected)
    m = len(y)
    draws = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, m, m)
        yy, pp = y[idx], p[idx]
        draws[i] = yy[pp].mean() / yy[~pp].mean()
    a = (1 - level) / 2
    lo, hi = np.quantile(draws, [a, 1 - a])
    return float(lo), float(hi)


# ------------------------------------------ calibration within groups

def calibration(promised, bad, group, band) -> pd.DataFrame:
    """For each band and group: loans, bads, the bad rate seen and the
    bad rate the score promised."""
    t = pd.DataFrame({"band": np.asarray(band), "g": np.asarray(group),
                      "bad": np.asarray(bad, dtype=float),
                      "p": np.asarray(promised, dtype=float)})
    out = t.groupby(["band", "g"], sort=True, observed=True).agg(
        n=("bad", "size"), bads=("bad", "sum"), seen=("bad", "mean"),
        promised=("p", "mean"))
    out["bads"] = out["bads"].astype(int)
    return out


def group_effect(promised, bad, x) -> dict[str, float]:
    """Does `x` (a group indicator, or a number such as age in decades)
    predict going bad once the score's own promise is known? A logistic
    regression of bad on the promise's log odds and `x`: a coefficient
    on `x` near zero says the score treats the group as it should."""
    p = np.clip(np.asarray(promised, dtype=float), 1e-6, 1 - 1e-6)
    X = sm.add_constant(pd.DataFrame({"score": np.log(p / (1 - p)),
                                      "x": np.asarray(x, dtype=float)}))
    r = sm.Logit(np.asarray(bad, dtype=float), X).fit(disp=0)
    return {"coef": float(r.params["x"]), "se": float(r.bse["x"]),
            "p": float(r.pvalues["x"]),
            "slope": float(r.params["score"])}


# ------------------------------------------------------- proxies

def separation(x, flag) -> float:
    """How well `x` alone tells the flagged group from the rest: the
    AUC of ranking by `x`, folded so that 0.5 means not at all and 1.0
    perfectly, whichever way round. A categorical `x` is ranked by each
    category's share of the flagged group (which flatters it a little,
    since the ranking is learned from the same rows). Missing values
    are left out."""
    s = pd.Series(x).reset_index(drop=True)
    y = np.asarray(flag, dtype=float)
    numeric = (pd.api.types.is_numeric_dtype(s)
               and not pd.api.types.is_bool_dtype(s))
    if not numeric:
        s = s.astype(str)
        s = s.map(pd.Series(y).groupby(s).mean())
    v = pd.to_numeric(s, errors="coerce").astype(float).to_numpy()
    keep = ~np.isnan(v)
    v, y = v[keep], y[keep]
    r = rankdata(v)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    auc = (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    return float(max(auc, 1 - auc))


# ---------------------------------------- reasons against the cut-off

def cutoff_reference(card: points.Scorecard, chars: pd.DataFrame,
                     cutoff: int, width: int = REFERENCE_WIDTH
                     ) -> pd.Series:
    """The average points on each line of the applicants who scored
    at the cut-off (from `cutoff` to `cutoff + width - 1`): what an
    applicant who only just passed typically had."""
    score = card.score(chars)
    at = ((score >= cutoff) & (score < cutoff + width)).to_numpy()
    if not at.any():
        raise ValueError("no applicant scored at the cut-off")
    return card.line_points(chars)[at].mean().rename("reference")


def gaps(card: points.Scorecard, chars: pd.DataFrame,
         reference: pd.Series) -> pd.DataFrame:
    """Points below the reference on each line (negative where the
    applicant did better than those at the cut-off). Each row adds up
    to the reference applicant's score less the applicant's own."""
    pts = card.line_points(chars)
    return reference[pts.columns] - pts


def cutoff_reasons(card: points.Scorecard, chars: pd.DataFrame,
                   reference: pd.Series, k: int = REASONS
                   ) -> pd.Series:
    """Up to `k` reasons per applicant: the lines furthest below the
    reference, largest first, with no bureau file said once."""
    g = gaps(card, chars, reference)
    nofile = chars["bureau_score"].isna().to_numpy()
    return pd.Series([reasons_for(g.iloc[i], bool(nofile[i]), k)
                      for i in range(len(g))], index=chars.index,
                     name="reasons")
