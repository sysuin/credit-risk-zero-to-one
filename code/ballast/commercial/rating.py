"""Internal ratings: Fernhill's master scale, a rating model for its
commercial clients, and the record of the analysts' judgement.

A rating is an opinion about a borrower's chance of default, written
as a grade. Fernhill's grades run from 1 (safest) to 10, plus D for a
borrower in default, and its master scale gives each grade one
probability of default over the next year. The module:

- holds the master scale and turns a PD into a grade and back;
- assembles every annual review: the accounts it was made on, the
  ratios, the analysts' grade, the model's grade, whether the analyst
  held the grade against the model, and whether the client defaulted
  within the year after the review;
- fits a rating model on a few ratios with a penalty that shrinks
  the coefficients towards zero, because a portfolio with a few dozen
  defaults cannot support more;
- measures how the analysts moved their grades against the model;
- records an override: who moved the model's grade, how far, why.

    import fernhill
    from ballast.commercial import rating as rt
    con = fernhill.connect()
    rv = rt.reviews(con)                   # one row per review
    dev = rv[rv.window_complete]
    model = rt.fit(rt.features(dev), dev.default_12m, penalty=3.0)
    model.grade(rt.features(dev))          # 1..10 on the master scale
"""
from __future__ import annotations

import datetime as dt
import json
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq, minimize

from ballast.commercial import spreading as sp
from ballast.config import AS_OF, BALLAST

# Fernhill's master scale: one PD over the next year for each grade.
# The PDs roughly double from one grade to the next. Grade D is a
# borrower in default (PD 100%).
MASTER_SCALE = {1: 0.0003, 2: 0.0007, 3: 0.0015, 4: 0.003,
                5: 0.006, 6: 0.012, 7: 0.024, 8: 0.05, 9: 0.10,
                10: 0.20}
GRADES = list(MASTER_SCALE)
DEFAULT = "D"
HORIZON_MONTHS = 12          # a grade's PD is for the next 12 months

# The model's inputs, and the range each ratio is held to. A company
# with EBITDA at or below zero has no meaningful leverage or cover; it
# is given the worst end of each range, which is where it belongs.
FEATURES = ["ln_leverage", "ln_cover", "equity_ratio", "size"]
SHORT = {"ln_leverage": "leverage", "ln_cover": "cover",
         "equity_ratio": "equity", "size": "size"}
LEVERAGE_RANGE = (0.25, 40.0)     # debt / EBITDA, times
COVER_RANGE = (0.25, 40.0)        # EBITDA / interest, times
RATING = BALLAST / "rating"


# ------------------------------------------------------ master scale

def pd_of(grade) -> float:
    """The master scale's PD for a grade (1.0 for D)."""
    if grade == DEFAULT:
        return 1.0
    return MASTER_SCALE[int(grade)]


def band_edges() -> np.ndarray:
    """The PD at which each grade gives way to the next.

    Each edge is the geometric mean of the two grades' PDs, so a PD
    belongs to the grade whose PD it is closest to on a log scale.
    """
    p = np.array(list(MASTER_SCALE.values()))
    return np.sqrt(p[:-1] * p[1:])


def grade_of(pd_) -> np.ndarray:
    """The master-scale grade for each PD."""
    p = np.asarray(pd_, dtype=float)
    return np.searchsorted(band_edges(), p, side="right") + 1


# ----------------------------------------------------------- reviews

def reviews(con) -> pd.DataFrame:
    """Every annual review of a commercial client, with its evidence.

    Fernhill reviews each client once a year, dated 31 March, on the
    accounts for the year just ended. Each row carries those accounts
    (derived as `spreading.derive` does), their ratios, the analysts'
    grade (`grade`), the rating model's (`model_grade`), whether the
    analyst held the grade against the model (`held`), the default
    month if the client ever defaulted, `default_12m` (a default in
    the 12 months after the review) and `window_complete` (those 12
    months have passed by AS_OF).
    """
    cols = ", ".join(f"f.{c}_cents AS {c}" for c in sp.RAW)
    raw = con.execute(f"""
        SELECT f.company_id, f.fiscal_year, {cols}, f.basis,
               c.name, c.sector, r.rating_date AS review_date,
               r.internal_grade AS grade, r.model_grade,
               r.analyst_override AS held, d.default_month
        FROM ratings r
        JOIN financials f
          ON f.company_id = r.company_id
         AND f.fiscal_year = year(r.rating_date) - 1
        JOIN companies c ON c.company_id = r.company_id
        LEFT JOIN corporate_defaults d
          ON d.company_id = r.company_id
        WHERE r.internal_grade IS NOT NULL
        ORDER BY r.company_id, r.rating_date""").df()
    d = sp.derive(raw)
    out = pd.concat([d, sp.ratio_frame(d)], axis=1)
    out["grade"] = out["grade"].astype(int)
    out["model_grade"] = out["model_grade"].astype(int)
    out["held"] = out["held"].astype(bool)
    review = pd.to_datetime(out["review_date"])
    end = review + pd.DateOffset(months=HORIZON_MONTHS)
    dflt = pd.to_datetime(out["default_month"])
    out["default_12m"] = ((dflt > review) & (dflt <= end)).astype(int)
    out["window_complete"] = end <= pd.Timestamp(AS_OF)
    return out.reset_index(drop=True)


def features(frame: pd.DataFrame) -> pd.DataFrame:
    """The rating model's inputs, from rows of derived accounts.

    ln_leverage   log of debt / EBITDA, held to LEVERAGE_RANGE
    ln_cover      log of EBITDA / interest, held to COVER_RANGE
    equity_ratio  equity / total assets
    size          log10 of revenue in dollars
    """
    ebitda = frame["ebitda"].astype(float)
    lev = frame["total_debt"] / ebitda.where(ebitda > 0)
    cover = ebitda / frame["interest"].astype(float).where(
        frame["interest"] > 0)
    lev = lev.fillna(LEVERAGE_RANGE[1]).clip(*LEVERAGE_RANGE)
    cover = cover.where(ebitda > 0, COVER_RANGE[0])
    cover = cover.fillna(COVER_RANGE[1]).clip(*COVER_RANGE)
    return pd.DataFrame({
        "ln_leverage": np.log(lev.astype(float)),
        "ln_cover": np.log(cover.astype(float)),
        "equity_ratio": (frame["equity"]
                         / frame["total_assets"]).astype(float),
        "size": np.log10(frame["revenue"].astype(float) / 100),
    }, index=frame.index)[FEATURES]


# ------------------------------------------------------------- model

@dataclass
class RatingModel:
    """A logistic model of default within a year, on standardised
    inputs: log odds = intercept + sum of coef x (x - mean) / scale."""
    names: list[str]
    mean: list[float]
    scale: list[float]
    intercept: float
    coef: list[float]
    penalty: float
    rows: int = 0
    defaults: int = 0
    note: str = ""

    def _z(self, F: pd.DataFrame) -> np.ndarray:
        X = F[self.names].to_numpy(dtype=float)
        return (X - np.array(self.mean)) / np.array(self.scale)

    def log_odds(self, F: pd.DataFrame) -> pd.Series:
        """Log odds of default (higher is riskier)."""
        lo = self.intercept + self._z(F) @ np.array(self.coef)
        return pd.Series(lo, index=F.index, name="log_odds")

    def pd(self, F: pd.DataFrame) -> pd.Series:
        """The model's PD over the next year."""
        return (1 / (1 + np.exp(-self.log_odds(F)))).rename("pd")

    def grade(self, F: pd.DataFrame) -> pd.Series:
        """The PD placed on the master scale."""
        return pd.Series(grade_of(self.pd(F)), index=F.index,
                         name="grade")

    def contributions(self, row: pd.Series) -> pd.Series:
        """Each input's part of one borrower's log odds, measured
        from an average borrower in the development sample."""
        z = (row[self.names].to_numpy(dtype=float)
             - np.array(self.mean)) / np.array(self.scale)
        return pd.Series(z * np.array(self.coef), index=self.names)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RatingModel":
        return cls(**d)


def _nll(beta, Z, y, penalty):
    """Penalised negative log-likelihood and its gradient."""
    eta = beta[0] + Z @ beta[1:]
    p = 1 / (1 + np.exp(-eta))
    nll = -(y * eta - np.logaddexp(0, eta)).sum()
    nll += 0.5 * penalty * (beta[1:] ** 2).sum()
    resid = y - p
    grad = -np.concatenate([[resid.sum()], Z.T @ resid])
    grad[1:] += penalty * beta[1:]
    return nll, grad


def fit(F: pd.DataFrame, default: pd.Series,
        penalty: float = 0.0) -> RatingModel:
    """Fit a logistic model of default with a ridge penalty.

    The inputs are standardised first, so one penalty treats every
    coefficient alike. The penalty adds `penalty / 2` times the sum of
    squared coefficients to the negative log-likelihood, which is the
    same as a normal prior centred on zero with variance 1 / penalty:
    a coefficient must earn its size from the data. The intercept is
    not penalised, so the average fitted PD equals the sample's
    default rate.
    """
    X = F.to_numpy(dtype=float)
    mean, scale = X.mean(axis=0), X.std(axis=0, ddof=1)
    Z = (X - mean) / scale
    y = np.asarray(default, dtype=float)
    start = np.zeros(Z.shape[1] + 1)
    start[0] = np.log(y.mean() / (1 - y.mean()))
    res = minimize(_nll, start, args=(Z, y, penalty), jac=True,
                   method="BFGS", options={"gtol": 1e-8})
    return RatingModel(names=list(F.columns), mean=mean.tolist(),
                       scale=scale.tolist(), intercept=float(res.x[0]),
                       coef=res.x[1:].tolist(), penalty=float(penalty),
                       rows=len(y), defaults=int(y.sum()))


def log_loss(p, default) -> float:
    """Average negative log-likelihood of the outcomes: lower is
    better, and it punishes confident mistakes hardest."""
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    y = np.asarray(default, dtype=float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def cross_validate(F: pd.DataFrame, default: pd.Series,
                   groups: pd.Series, penalty: float) -> pd.Series:
    """Each row's PD from a model fitted without its group.

    With groups set to the review year, every year is scored by a
    model that never saw it: the nearest a few dozen defaults allow
    to an out-of-time test.
    """
    out = pd.Series(np.nan, index=F.index, name="pd")
    for g in sorted(groups.unique()):
        test = (groups == g).to_numpy()
        m = fit(F[~test], default[~test], penalty)
        out[test] = m.pd(F[test]).to_numpy()
    return out


def penalty_path(F: pd.DataFrame, default: pd.Series,
                 groups: pd.Series, grid) -> pd.DataFrame:
    """Cross-validated log loss for each penalty, and the fitted
    coefficients on all rows at that penalty."""
    rows = []
    for lam in grid:
        p = cross_validate(F, default, groups, lam)
        m = fit(F, default, lam)
        rows.append({"penalty": lam, "cv_log_loss":
                     log_loss(p, default),
                     **dict(zip(m.names, m.coef))})
    return pd.DataFrame(rows).set_index("penalty")


def recalibrate(model: RatingModel, F: pd.DataFrame,
                target: float) -> RatingModel:
    """The same model with its intercept moved so that the average
    PD over the rows of F is `target`. The ranking is unchanged."""
    lo = model.log_odds(F).to_numpy() - model.intercept

    def gap(a):
        return (1 / (1 + np.exp(-(a + lo)))).mean() - target

    new = RatingModel.from_dict(model.to_dict())
    new.intercept = float(brentq(gap, -30, 30))
    return new


def save_model(model: RatingModel, path: Path = RATING) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    out = path / "model.json"
    out.write_text(json.dumps(model.to_dict(), indent=2) + "\n")
    return out


def load_model(path: Path = RATING) -> RatingModel:
    return RatingModel.from_dict(json.loads(
        (path / "model.json").read_text()))


# ----------------------------------------------- how analysts moved

def moves(rv: pd.DataFrame) -> pd.DataFrame:
    """Each review with a previous grade: where the model would have
    taken the grade, and where the analyst did.

    wanted  model grade less last year's grade (+ is a downgrade)
    moved   this year's grade less last year's
    held    the model wanted a move and the grade did not change
    """
    r = rv.sort_values(["company_id", "review_date"]).copy()
    r["previous"] = r.groupby("company_id")["grade"].shift(1)
    r = r[r["previous"].notna()].copy()
    r["previous"] = r["previous"].astype(int)
    r["wanted"] = r["model_grade"] - r["previous"]
    r["moved"] = r["grade"] - r["previous"]
    r["held_found"] = (r["moved"] == 0) & (r["wanted"] != 0)
    return r


def stickiness(m: pd.DataFrame) -> pd.DataFrame:
    """How far the analysts moved, by how far the model wanted to.

    For each size of wanted move (in notches, either direction): the
    reviews, the share moved one notch, the share taken all the way
    to the model's grade, and the share held.
    """
    size = m["wanted"].abs().clip(upper=4)
    rows = []
    for k, g in m[size > 0].groupby(size[size > 0]):
        rows.append({"wanted": int(k), "reviews": len(g),
                     "one_notch": (g.moved.abs() == 1).mean(),
                     "to_model": (g.grade == g.model_grade).mean(),
                     "held": g.held_found.mean()})
    return pd.DataFrame(rows).set_index("wanted")


# --------------------------------------------------------- overrides

@dataclass
class Override:
    """An analyst's grade that differs from the model's, on record.

    Every override names the model's grade, the grade assigned, the
    reasons, who made it, and what evidence would end it. An override
    without reasons is refused.
    """
    company: str
    review_date: dt.date
    model_grade: int
    grade: int
    reasons: list[str] = field(default_factory=list)
    by: str = ""
    revisit_when: str = ""

    def __post_init__(self):
        for g in (self.model_grade, self.grade):
            if g not in MASTER_SCALE:
                raise ValueError(f"no grade {g!r} on the scale")
        if self.grade != self.model_grade and not self.reasons:
            raise ValueError("an override needs its reasons")

    @property
    def notches(self) -> int:
        """Positive when the analyst is more cautious than the
        model."""
        return self.grade - self.model_grade

    @property
    def pd(self) -> float:
        return pd_of(self.grade)

    def lines(self, width: int = 68) -> list[str]:
        """The record as it is filed, wrapped to `width`."""
        out = [f"{self.company}, review {self.review_date:%d %b %Y}",
               f"model grade {self.model_grade} "
               f"(PD {pd_of(self.model_grade):.2%}); assigned "
               f"{self.grade} (PD {self.pd:.2%}); "
               f"{self.notches:+d} notches"]
        for i, r in enumerate(self.reasons, 1):
            out += textwrap.wrap(f"{i}. {r}", width,
                                 subsequent_indent="   ")
        out += textwrap.wrap(f"Revisit: {self.revisit_when}", width,
                             subsequent_indent="   ")
        out.append(f"By: {self.by}")
        return out
