"""Mark II's model: a logistic regression on WoE-coded characteristics.

The regression models the log of the odds of a loan being good, as a
constant plus one coefficient for each characteristic times the
applicant's weight of evidence on it. Weight of evidence is itself a
log of odds (positive is safer), so every coefficient should come out
positive: more evidence of safety, better odds. A negative coefficient
is a **wrong sign**, and a scorecard with one pays applicants for
looking riskier. `select` refuses any step that produces one.

Every bureau characteristic has a "no file" bin, and the same few
hundred applicants sit in all of them. Coded as they are, a model sees
the absence of a file once for every bureau column it uses. The
`separate_no_file` design moves that evidence into one characteristic
of its own, `bureau_file`, and makes "no file" neutral (WoE 0)
everywhere else.

    from ballast.scorecard import model
    frame = model.with_file_flag(sample_rows)
    binset = model.separate_no_file(binset, train, train["bad"])
    X = woe.encode(frame, binset)
    chosen, steps = model.select(X[fit], model.target(train),
                                 candidates, force=["bureau_file"])
    result = model.fit(X[fit], model.target(train), chosen)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2

from ballast.config import TODAY
from ballast.scorecard import woe
from ballast.scorecard.binning import Bins
from ballast.scorecard.sample import MARK2, NO_FILE

ALPHA = 0.05                 # a characteristic must earn its place
FILE_FLAG = "bureau_file"    # file or no file, as one characteristic
FILE_SOURCE = "bureau_score"     # missing exactly when there is no file
SPLITS = ("train", "holdout", "out_of_time")
# Mark II's characteristics, as Chapter 8 chose them: forward selection
# with the sign rule, on the design with one line for "no file", which
# is forced in. In the order they entered.
CHARACTERISTICS = ["bureau_file", "enquiries_6m", "bureau_score",
                   "oldest_account_months", "address_months", "dti",
                   "income", "revolving_utilisation",
                   "revolving_balance"]


# ------------------------------------------------------------ inputs

def target(frame: pd.DataFrame) -> pd.Series:
    """1 for a good loan, 0 for a bad one: the model's odds are
    good to bad, the same way round as weight of evidence."""
    return (1 - frame["bad"]).astype(int).rename("good")


def with_file_flag(frame: pd.DataFrame) -> pd.DataFrame:
    """A copy of `frame` with a `bureau_file` column: file / no file."""
    out = frame.copy()
    out[FILE_FLAG] = np.where(out[FILE_SOURCE].isna(), NO_FILE, "file")
    return out


def separate_no_file(binset: dict[str, Bins], train: pd.DataFrame,
                     bad: pd.Series) -> dict[str, Bins]:
    """The no-file evidence in one place.

    Returns new bins (the originals are untouched): every bureau
    characteristic's "no file" bin gets a WoE of 0, and a
    `bureau_file` characteristic, fitted on `train`, carries the
    difference between applicants with a file and without one.
    """
    out = {}
    for name, b in binset.items():
        if b.missing == NO_FILE:
            b = replace(b, woe=b.woe | {NO_FILE: 0.0})
        out[name] = b
    flag = Bins(FILE_FLAG, "categorical",
                groups=[["file"], [NO_FILE]])
    woe.fit(flag, with_file_flag(train)[FILE_FLAG], bad)
    out[FILE_FLAG] = flag
    return out


# --------------------------------------------------------------- fit

def fit(X: pd.DataFrame, good: pd.Series, cols: list[str]):
    """Maximum-likelihood logistic regression of `good` on `cols`."""
    design = sm.add_constant(X[list(cols)], has_constant="add")
    return sm.Logit(good.to_numpy(), design).fit(
        method="newton", maxiter=100, disp=0)


def coefficients(result) -> pd.DataFrame:
    """One row per term: estimate, standard error, z, p, sign."""
    t = pd.DataFrame({"coef": result.params, "se": result.bse,
                      "z": result.tvalues, "p": result.pvalues})
    t["sign_ok"] = (t["coef"] > 0) | (t.index == "const")
    return t


def wrong_signs(result) -> list[str]:
    t = coefficients(result)
    return [n for n in t.index if not t.loc[n, "sign_ok"]]


def log_odds(result, X: pd.DataFrame) -> pd.Series:
    """The fitted log of the odds good:bad for every row of X."""
    names = [n for n in result.params.index if n != "const"]
    lo = result.params["const"] + X[names].to_numpy() @ \
        result.params[names].to_numpy()
    return pd.Series(lo, index=X.index, name="log_odds")


def bad_rate(result, X: pd.DataFrame) -> pd.Series:
    """The fitted probability that each row goes bad."""
    return (1 / (1 + np.exp(log_odds(result, X)))).rename("p_bad")


def fit_mark2(s: pd.DataFrame, binset: dict[str, Bins],
              cols: list[str] = CHARACTERISTICS):
    """Mark II fitted on the sample's training loans.

    Returns the fitted result and the bins it uses (no-file evidence
    in `bureau_file`, neutral elsewhere)."""
    train = with_file_flag(s[s["fit"]])
    design = separate_no_file(binset, train, train["bad"])
    bins = {n: design[n] for n in cols}
    X = woe.encode(train, bins)
    return fit(X, target(train), cols), bins


# --------------------------------------------------------- selection

@dataclass
class Step:
    """One round of forward selection."""
    added: str | None
    lr: float                       # likelihood-ratio statistic
    p: float
    wrong_sign: list[str] = field(default_factory=list)


def select(X: pd.DataFrame, good: pd.Series, candidates: list[str],
           force: tuple[str, ...] | list[str] = (),
           alpha: float = ALPHA) -> tuple[list[str], list[Step]]:
    """Forward selection with a sign rule.

    Start from the characteristics in `force`. In each round, try
    every remaining candidate; refuse any whose entry leaves a
    coefficient (its own or another's) with the wrong sign; add the
    one that improves the likelihood most, if its likelihood-ratio
    test has p below `alpha`. Stop when none qualifies.
    """
    chosen, steps = list(force), []
    left = [c for c in candidates if c not in chosen]
    current = fit(X, good, chosen).llf
    while left:
        best, refused = None, []
        for c in left:
            r = fit(X, good, chosen + [c])
            if wrong_signs(r):
                refused.append(c)
                continue
            lr = 2 * (r.llf - current)
            if best is None or lr > best[1]:
                best = (c, lr, r.llf)
        if best is None or chi2.sf(best[1], 1) >= alpha:
            lr = best[1] if best else float("nan")
            steps.append(Step(None, lr, float(chi2.sf(lr, 1))
                              if best else float("nan"), refused))
            break
        c, lr, current = best
        steps.append(Step(c, lr, float(chi2.sf(lr, 1)), refused))
        chosen.append(c)
        left.remove(c)
    return chosen, steps


# --------------------------------------------------------- stability

def stability(X: pd.DataFrame, good: pd.Series, split: pd.Series,
              cols: list[str], splits=SPLITS) -> pd.DataFrame:
    """Refit the same characteristics on each split on its own.

    For each characteristic: the coefficient and standard error in
    every split, and how far each later split's estimate sits from
    the first's, in standard errors of the difference.
    """
    rows = {}
    fits = {s: fit(X[split == s], good[split == s], cols)
            for s in splits}
    base = splits[0]
    for name in ["const"] + list(cols):
        row = {}
        for s in splits:
            row[f"{s}_coef"] = fits[s].params[name]
            row[f"{s}_se"] = fits[s].bse[name]
        for s in splits[1:]:
            gap = row[f"{s}_coef"] - row[f"{base}_coef"]
            se = np.hypot(row[f"{s}_se"], row[f"{base}_se"])
            row[f"{s}_z"] = gap / se
        rows[name] = row
    return pd.DataFrame(rows).T


# -------------------------------------------------------------- save

def save_model(result, cols: list[str], binset: dict[str, Bins],
               path: Path = MARK2, steps: list[Step] | None = None,
               force: list[str] | None = None) -> Path:
    """Write the fitted model and the bins it was fitted with."""
    t = coefficients(result)
    out = {
        "model": "logistic regression of good (1) vs bad (0) "
                 "on WoE-coded characteristics",
        "fitted": str(TODAY),
        "n": int(result.nobs),
        "goods": int(result.model.endog.sum()),
        "characteristics": list(cols),
        "forced": list(force or []),
        "alpha": ALPHA,
        "coefficients": {n: {k: round(float(t.loc[n, k]), 6)
                             for k in ("coef", "se", "p")}
                         for n in t.index},
        "log_likelihood": round(float(result.llf), 4),
        "null_log_likelihood": round(float(result.llnull), 4),
        "selection": [{"added": s.added, "lr": round(s.lr, 4),
                       "p": round(s.p, 6), "wrong_sign": s.wrong_sign}
                      for s in (steps or [])],
        "bins": {n: binset[n].to_dict() for n in cols},
    }
    path.mkdir(parents=True, exist_ok=True)
    f = path / "model.json"
    f.write_text(json.dumps(out, indent=2) + "\n")
    return f


def load_model(path: Path = MARK2) -> dict:
    """The saved model: its coefficients and its bins, ready to use."""
    d = json.loads((path / "model.json").read_text())
    d["coef"] = {n: v["coef"] for n, v in d["coefficients"].items()}
    d["binset"] = {n: Bins.from_dict(v) for n, v in d["bins"].items()}
    return d
