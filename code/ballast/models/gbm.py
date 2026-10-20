"""The challenger: gradient-boosted trees on raw characteristics.

Mark II reads nine characteristics through coarse bins and adds up
their evidence. The challenger reads all twenty-one candidates Chapter
7 measured, as they are (no bins, no WoE; a missing value stays
missing), and adds up a few hundred small decision trees, each fitted
to what the trees before it got wrong. LightGBM does the fitting.

Three rules make it a model a lender can defend:

- **Monotone constraints** where credit logic leaves no room for
  argument: a higher bureau score never raises the predicted risk;
  more enquiries, worse arrears, more public records, a higher
  debt-to-income ratio and higher card utilisation never lower it.
- **Early stopping on a fold carved from the training loans only**:
  the holdout and out-of-time loans are never used to choose
  anything. Once the number of trees is chosen, the model is refitted
  on all the training loans with that many trees.
- **Single-threaded and seeded**, so that it prints the same numbers
  on every run.

The model predicts the chance of going bad. `score` puts it on Mark
II's scale (600 points at odds of 50 to 1, 20 points to double the
odds), so the two can be read side by side.

    from ballast.models import gbm
    model = gbm.fit(s)                    # s from sample.load_sample()
    model.score(s)                        # Mark II's scale
    gbm.save(model); model = gbm.load()   # data/ballast/challenger/
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from ballast.config import BALLAST, SEED
from ballast.scorecard import points, sample

CHALLENGER = BALLAST / "challenger"
FEATURES = sample.NUMERIC + sample.CATEGORICAL
CATEGORICAL = sample.CATEGORICAL
# +1: the predicted risk may only rise as the characteristic rises;
# -1: it may only fall. Everything else is left to the data.
MONOTONE = {
    "bureau_score": -1,           # the bureau's own ranking of risk
    "enquiries_6m": +1,           # more searches for credit
    "worst_status_24m": +1,       # worse recent arrears
    "public_records": +1,         # judgments, insolvencies
    "dti": +1,                    # more of the income already owed
    "revolving_utilisation": +1,  # more of the card limits used
}
PARAMS = {
    "objective": "binary",        # the log odds of going bad
    "learning_rate": 0.02,        # each tree corrects a little
    "num_leaves": 7,              # small trees
    "min_data_in_leaf": 100,      # no leaf rests on a handful
    "feature_fraction": 0.8,      # each tree sees 80% of the fields
    "bagging_fraction": 0.8,      # ... and 80% of the loans
    "bagging_freq": 1,
    "lambda_l2": 10.0,            # shrink leaf values towards zero
    "num_threads": 1,
    "deterministic": True,
    "force_row_wise": True,
    "verbose": -1,
}
VALIDATION_SHARE = 0.20
MAX_ROUNDS = 3000
PATIENCE = 100                    # rounds without improvement


# ------------------------------------------------------------ inputs

def categories(frame: pd.DataFrame,
               cols: list[str] = CATEGORICAL) -> dict[str, list[str]]:
    """Each categorical's values, sorted: fixed once, on training."""
    return {c: sorted(frame[c].dropna().astype(str).unique())
            for c in cols if c in frame}


def design(frame: pd.DataFrame, features: list[str],
           cats: dict[str, list[str]]) -> pd.DataFrame:
    """The columns LightGBM reads: numbers as floats (missing stays
    missing), categoricals with the training categories (an unseen
    value becomes missing)."""
    out = pd.DataFrame(index=frame.index)
    for f in features:
        if f in cats:
            v = frame[f].astype(str)
            out[f] = pd.Categorical(v.where(v.isin(cats[f])),
                                    categories=cats[f])
        else:
            out[f] = frame[f].astype("float64")
    return out


def constraints(features: list[str],
                monotone: dict[str, int]) -> list[int]:
    return [int(monotone.get(f, 0)) for f in features]


def validation_fold(bad: pd.Series, share: float = VALIDATION_SHARE,
                    seed: int = SEED) -> pd.Series:
    """A random `share` of the rows, the same share of goods and of
    bads, the same on every run. True marks the validation rows."""
    rng = np.random.default_rng(seed)
    y = bad.to_numpy()
    out = np.zeros(len(y), dtype=bool)
    for k in (0, 1):
        rows = np.flatnonzero(y == k)
        out[rng.choice(rows, round(share * len(rows)),
                       replace=False)] = True
    return pd.Series(out, index=bad.index, name="validation")


# ------------------------------------------------------------- model

@dataclass
class Challenger:
    """A fitted booster and everything needed to use it again."""
    booster: lgb.Booster
    features: list[str]
    categories: dict[str, list[str]]
    monotone: dict[str, int]
    params: dict
    rounds: int
    history: list[float] = field(default_factory=list)

    def _x(self, frame: pd.DataFrame) -> pd.DataFrame:
        return design(frame, self.features, self.categories)

    def raw(self, frame: pd.DataFrame) -> np.ndarray:
        """Log odds of going bad."""
        return self.booster.predict(self._x(frame), raw_score=True)

    def p_bad(self, frame: pd.DataFrame) -> pd.Series:
        return pd.Series(1 / (1 + np.exp(-self.raw(frame))),
                         index=frame.index, name="p_bad")

    def score(self, frame: pd.DataFrame) -> pd.Series:
        """On Mark II's scale: higher is safer, unrounded."""
        return pd.Series(points.score_from_log_odds(-self.raw(frame)),
                         index=frame.index, name="challenger")

    def contributions(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Each characteristic's share of each row's log odds of going
        bad (TreeSHAP), and `bias`, the part every row shares. Each
        row adds up to `raw`."""
        c = self.booster.predict(self._x(frame), pred_contrib=True)
        return pd.DataFrame(c, index=frame.index,
                            columns=self.features + ["bias"])


def _train(params, X, y, rounds, valid=None):
    data = lgb.Dataset(X, y, free_raw_data=False)
    if valid is None:
        return lgb.train(params, data, rounds), []
    vX, vy = valid
    vdata = lgb.Dataset(vX, vy, reference=data)
    record: dict = {}
    booster = lgb.train(
        params, data, rounds, valid_sets=[vdata],
        callbacks=[lgb.early_stopping(PATIENCE, verbose=False),
                   lgb.record_evaluation(record)])
    return booster, record["valid_0"]["binary_logloss"]


def fit(s: pd.DataFrame, features: list[str] = FEATURES,
        monotone: dict[str, int] = MONOTONE, seed: int = SEED,
        params: dict | None = None, rows: str = "fit") -> Challenger:
    """The challenger, fitted on the sample's training loans.

    A validation fold is carved from the training loans (`rows`, by
    default the sample's `fit` flag) and used for one thing: to stop
    adding trees when its log loss stops improving. The model is then
    refitted on every training loan with that number of trees.
    """
    train = s[s[rows]]
    cats = categories(train, [f for f in features if f in CATEGORICAL])
    p = PARAMS | {"seed": seed} | (params or {})
    p["monotone_constraints"] = constraints(features, monotone)
    X, y = design(train, features, cats), train["bad"].to_numpy()
    val = validation_fold(train["bad"], seed=seed).to_numpy()
    probe, history = _train(p, X[~val], y[~val], MAX_ROUNDS,
                            valid=(X[val], y[val]))
    rounds = probe.best_iteration
    booster, _ = _train(p, X, y, rounds)
    return Challenger(booster, list(features), cats, dict(monotone),
                      p, rounds, history)


# ----------------------------------------------------------- inspect

def partial_dependence(model: Challenger, frame: pd.DataFrame,
                       feature: str, grid) -> pd.Series:
    """The average log odds of going bad over `frame`, with `feature`
    set to each value of `grid` for every row in turn."""
    out = {}
    for v in grid:
        f = frame.copy()
        f[feature] = v
        out[v] = float(model.raw(f).mean())
    return pd.Series(out, name=feature)


def wrong_way(model: Challenger, frame: pd.DataFrame, feature: str,
              step: float, riskier: int = +1,
              tol: float = 1e-9) -> float:
    """The share of rows whose predicted risk falls when `feature`
    moves by `step` in the direction credit logic calls riskier
    (`riskier` +1: upwards; -1: downwards). Rows missing the feature
    are left out."""
    f = frame[frame[feature].notna()]
    moved = f.copy()
    moved[feature] = f[feature] + riskier * step
    return float((model.raw(moved) < model.raw(f) - tol).mean())


def size(model: Challenger) -> dict[str, int]:
    """How many trees, leaves and split rules the model holds."""
    d = model.booster.dump_model()["tree_info"]
    leaves = sum(t["num_leaves"] for t in d)
    return {"trees": len(d), "leaves": leaves,
            "splits": leaves - len(d)}


# -------------------------------------------------------------- save

def save(model: Challenger, path: Path = CHALLENGER,
         extra: dict | None = None) -> list[Path]:
    """model.txt (LightGBM's own text format) and challenger.json."""
    path.mkdir(parents=True, exist_ok=True)
    files = [path / "model.txt", path / "challenger.json"]
    model.booster.save_model(str(files[0]))
    files[1].write_text(json.dumps({
        "features": model.features, "categories": model.categories,
        "monotone": model.monotone,
        "params": {k: v for k, v in model.params.items()
                   if k != "monotone_constraints"},
        "rounds": model.rounds,
        "validation_logloss": [round(v, 6) for v in model.history],
        "scale": {"base_score": points.BASE_SCORE,
                  "base_odds": points.BASE_ODDS, "pdo": points.PDO},
    } | (extra or {}), indent=2) + "\n")
    return files


def load(path: Path = CHALLENGER) -> Challenger:
    d = json.loads((path / "challenger.json").read_text())
    booster = lgb.Booster(model_file=str(path / "model.txt"))
    p = d["params"] | {"monotone_constraints": constraints(
        d["features"], d["monotone"])}
    return Challenger(booster, d["features"], d["categories"],
                      d["monotone"], p, d["rounds"],
                      d["validation_logloss"])
