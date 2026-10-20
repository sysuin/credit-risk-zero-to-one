"""From a fitted model to a points table, and scoring with it.

A logistic regression on WoE produces a log of odds. A scorecard
states the same thing in points, on a scale the lender chooses once:
Mark II's says that 600 points means odds of 50 good loans to every
bad one, and that every 20 points doubles the odds (the **points to
double the odds**, PDO). Two numbers fix the straight line between
log odds and points:

    factor = PDO / ln 2
    offset = 600 - factor * ln 50
    score  = offset + factor * log odds

Each characteristic's points are factor x coefficient x WoE for its
bins, shifted so the riskiest bin earns 0; the constant and the shifts
go into a single **base** that every applicant receives. Everything is
rounded to whole points, as a printed table must be.

    from ballast.scorecard import points
    card = points.scorecard(coef, binset)      # base + table
    card.score(frame)                          # integer scores
    card.explain(frame.iloc[0])                # line by line
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ballast.scorecard.binning import Bins
from ballast.scorecard.model import FILE_FLAG, with_file_flag
from ballast.scorecard.sample import MARK2

BASE_SCORE = 600        # the score at which ...
BASE_ODDS = 50          # ... the odds are 50 good to 1 bad
PDO = 20                # points to double the odds
FACTOR = PDO / math.log(2)
OFFSET = BASE_SCORE - FACTOR * math.log(BASE_ODDS)


def score_from_log_odds(log_odds):
    return OFFSET + FACTOR * np.asarray(log_odds, dtype=float)


def odds_at(score):
    """Good:bad odds the scale assigns to a score."""
    return np.exp((np.asarray(score, dtype=float) - OFFSET) / FACTOR)


def bad_rate_at(score):
    """The bad rate those odds imply: 1 / (1 + odds)."""
    return 1 / (1 + odds_at(score))


@dataclass
class Scorecard:
    """A base and a points table: everything needed to score."""
    base: int
    table: pd.DataFrame        # characteristic, bin, woe, coef, points
    binset: dict[str, Bins]

    @property
    def characteristics(self) -> list[str]:
        return list(dict.fromkeys(self.table["characteristic"]))

    def _frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if FILE_FLAG in self.characteristics and \
                FILE_FLAG not in frame:
            frame = with_file_flag(frame)
        return frame

    def line_points(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Each row's points on each characteristic."""
        frame = self._frame(frame)
        out = {}
        for name in self.characteristics:
            pts = self.table.loc[self.table["characteristic"] == name,
                                 "points"].to_numpy()
            out[name] = pts[self.binset[name].index(frame[name])]
        return pd.DataFrame(out, index=frame.index)

    def score(self, frame: pd.DataFrame) -> pd.Series:
        """base + the sum of the points: whole numbers."""
        return (self.base + self.line_points(frame).sum(axis=1)
                ).astype(int).rename("mark2_score")

    def explain(self, row: pd.Series) -> pd.DataFrame:
        """One applicant's score, line by line: value, bin, points."""
        frame = self._frame(row.to_frame().T)
        lines = []
        for name in self.characteristics:
            b = self.binset[name]
            i = int(b.index(frame[name])[0])
            pts = self.table.loc[self.table["characteristic"] == name,
                                 "points"].to_numpy()[i]
            lines.append((name, frame[name].iloc[0], b.labels[i],
                          int(pts)))
        return pd.DataFrame(lines, columns=["characteristic", "value",
                                            "bin", "points"])


def scorecard(coef: dict[str, float],
              binset: dict[str, Bins]) -> Scorecard:
    """Scale a fitted model's coefficients into a points table."""
    rows, shifts = [], 0.0
    names = [n for n in coef if n != "const"]
    for name in names:
        b, c = binset[name], coef[name]
        raw = {lab: FACTOR * c * b.woe[lab] for lab in b.labels}
        low = min(raw.values())
        shifts += low
        for lab in b.labels:
            rows.append({"characteristic": name, "bin": lab,
                         "woe": b.woe[lab], "coef": c,
                         "exact": raw[lab] - low,
                         "points": int(round(raw[lab] - low))})
    base = OFFSET + FACTOR * coef["const"] + shifts
    table = pd.DataFrame(rows)
    return Scorecard(int(round(base)), table,
                     {n: binset[n] for n in names})


def exact_score(coef: dict[str, float], binset: dict[str, Bins],
                frame: pd.DataFrame) -> pd.Series:
    """The unrounded score, straight from the log odds."""
    if FILE_FLAG in coef and FILE_FLAG not in frame:
        frame = with_file_flag(frame)
    lo = np.full(len(frame), coef["const"])
    for name, c in coef.items():
        if name == "const":
            continue
        b = binset[name]
        w = np.array([b.woe[lab] for lab in b.labels])
        lo = lo + c * w[b.index(frame[name])]
    return pd.Series(score_from_log_odds(lo), index=frame.index)


# -------------------------------------------------------------- save

def save_scorecard(card: Scorecard, path: Path = MARK2) -> list[Path]:
    """points_table.csv for people; scorecard.json for Ballast."""
    path.mkdir(parents=True, exist_ok=True)
    csv = path / "points_table.csv"
    t = card.table[["characteristic", "bin", "points"]]
    pd.concat([pd.DataFrame([{"characteristic": "base", "bin": "",
                              "points": card.base}]), t]
              ).to_csv(csv, index=False)
    js = path / "scorecard.json"
    js.write_text(json.dumps({
        "scale": {"base_score": BASE_SCORE, "base_odds": BASE_ODDS,
                  "pdo": PDO, "factor": round(FACTOR, 6),
                  "offset": round(OFFSET, 6)},
        "base": card.base,
        "lines": {n: {"bins": card.binset[n].to_dict(),
                      "points": card.table.loc[
                          card.table["characteristic"] == n,
                          "points"].astype(int).tolist()}
                  for n in card.characteristics},
    }, indent=2) + "\n")
    return [csv, js]


def load_scorecard(path: Path = MARK2) -> Scorecard:
    d = json.loads((path / "scorecard.json").read_text())
    rows, binset = [], {}
    for name, line in d["lines"].items():
        b = Bins.from_dict(line["bins"])
        binset[name] = b
        for lab, pts in zip(b.labels, line["points"]):
            rows.append({"characteristic": name, "bin": lab,
                         "woe": b.woe.get(lab), "coef": None,
                         "exact": None, "points": int(pts)})
    return Scorecard(d["base"], pd.DataFrame(rows), binset)
