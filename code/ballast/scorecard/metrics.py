"""How good is a score? Ranking, separation and calibration.

Two different questions, and a scorecard must answer both.

**Ranking**: do the bads get lower scores than the goods? The
**AUC** is the chance that a randomly chosen good loan scores above a
randomly chosen bad one (ties count half); the **Gini** coefficient is
2 x AUC - 1, so 0 is a coin toss and 1 is perfect. The ROC and CAP
curves draw the same thing, and **KS** is the widest gap between the
share of bads and the share of goods below any one score.

**Calibration**: when the scale says 2% will go bad, do 2% go bad?
Group loans into score bands and compare the bad rate the score
implies with the one observed, band by band.

In every function here a higher score means a safer applicant, and
`bad` is 1 for a bad loan, 0 for a good one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest, chi2, rankdata


def _arrays(score, bad):
    s = np.asarray(score, dtype=float)
    b = np.asarray(bad, dtype=int)
    if s.shape != b.shape:
        raise ValueError("score and bad must be the same length")
    if b.min() == b.max():
        raise ValueError("need both goods and bads")
    return s, b


# ----------------------------------------------------------- ranking

def auc(score, bad) -> float:
    """P(a good scores above a bad), ties counted half."""
    s, b = _arrays(score, bad)
    r = rankdata(s)                       # average ranks for ties
    n_good, n_bad = int((b == 0).sum()), int(b.sum())
    rank_good = r[b == 0].sum()
    return float((rank_good - n_good * (n_good + 1) / 2)
                 / (n_good * n_bad))


def gini(score, bad) -> float:
    return 2 * auc(score, bad) - 1


def _cumulative(score, bad):
    """Shares of bads, goods and all loans at or below each distinct
    score, riskiest first, starting from (0, 0, 0)."""
    s, b = _arrays(score, bad)
    t = pd.DataFrame({"s": s, "b": b}).groupby("s")["b"].agg(
        ["sum", "count"]).sort_index()
    bads = np.concatenate([[0], t["sum"].cumsum()]) / b.sum()
    goods = np.concatenate([[0], (t["count"] - t["sum"]).cumsum()]
                           ) / (len(b) - b.sum())
    alls = np.concatenate([[0], t["count"].cumsum()]) / len(b)
    edge = np.concatenate([[t.index[0]], t.index.to_numpy()])
    return edge, bads, goods, alls


def roc_points(score, bad) -> pd.DataFrame:
    """The ROC curve: share of goods (x) and of bads (y) at or below
    each score. The area under it is the AUC."""
    edge, bads, goods, _ = _cumulative(score, bad)
    return pd.DataFrame({"score": edge, "goods": goods, "bads": bads})


def cap_points(score, bad) -> pd.DataFrame:
    """The CAP curve: share of all loans (x) and of bads (y) at or
    below each score, riskiest first."""
    edge, bads, _, alls = _cumulative(score, bad)
    return pd.DataFrame({"score": edge, "loans": alls, "bads": bads})


def ks(score, bad) -> tuple[float, float]:
    """The Kolmogorov-Smirnov statistic and the score where it falls:
    the largest gap between the share of bads and the share of goods
    at or below one score."""
    edge, bads, goods, _ = _cumulative(score, bad)
    gap = bads - goods
    i = int(np.argmax(gap))
    return float(gap[i]), float(edge[i])


# ------------------------------------------------------- uncertainty

def bootstrap(stat, *columns, n: int = 1000,
              rng: np.random.Generator) -> np.ndarray:
    """`stat` recomputed on `n` resamples of the rows, drawn with
    replacement. Pass several columns to keep rows together, which is
    what makes a comparison of two scores on the same loans paired."""
    cols = [np.asarray(c) for c in columns]
    m = len(cols[0])
    out = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, m, m)
        out[i] = stat(*(c[idx] for c in cols))
    return out


def interval(draws: np.ndarray, level: float = 0.95
             ) -> tuple[float, float]:
    """The central `level` share of bootstrap draws."""
    a = (1 - level) / 2
    lo, hi = np.quantile(draws, [a, 1 - a])
    return float(lo), float(hi)


# ------------------------------------------------------- calibration

def bands(score, edges: list[float]) -> pd.Series:
    """Label each score with its band: '<e0', 'e0-e1', ..., 'ek+'."""
    s = np.asarray(score, dtype=float)
    labels = [f"<{edges[0]:g}"] + [
        f"{a:g}-{b - 1:g}" for a, b in zip(edges[:-1], edges[1:])
    ] + [f"{edges[-1]:g}+"]
    i = np.searchsorted(np.asarray(edges, float), s, side="right")
    return pd.Series(pd.Categorical.from_codes(
        i, categories=labels, ordered=True))


def calibration(score, bad, p_bad, edges: list[float]) -> pd.DataFrame:
    """Predicted against observed bad rate by score band.

    `p_bad` is each loan's predicted chance of going bad. For each
    band: loans, bads, the observed rate, the mean predicted rate,
    the bads that prediction expects, and a two-sided binomial test
    of the observed count against the band's mean predicted rate (an
    approximation, since the loans in a band do not share one rate).
    """
    b = np.asarray(bad, dtype=int)
    p = np.asarray(p_bad, dtype=float)
    band = bands(score, edges)
    rows = []
    for lab in band.cat.categories:
        m = (band == lab).to_numpy()
        n, k = int(m.sum()), int(b[m].sum())
        if n == 0:
            continue
        pred = float(p[m].mean())
        rows.append({"band": lab, "loans": n, "bads": k,
                     "observed": k / n, "predicted": pred,
                     "expected": pred * n,
                     "p_value": binomtest(k, n, pred).pvalue})
    return pd.DataFrame(rows)


def hosmer_lemeshow(p_bad, bad, groups: int = 10,
                    fitted_here: bool = False
                    ) -> tuple[float, int, float]:
    """The Hosmer-Lemeshow statistic over groups of equal size by
    predicted rate: sum of (observed - expected)^2 / variance.

    On the loans a model was fitted to, the statistic is compared with
    chi-squared on groups - 2 degrees of freedom; on loans it never
    saw, on `groups`.
    """
    p = np.asarray(p_bad, dtype=float)
    b = np.asarray(bad, dtype=int)
    order = np.argsort(p, kind="stable")
    stat = 0.0
    for idx in np.array_split(order, groups):
        n, e, o = len(idx), p[idx].sum(), b[idx].sum()
        stat += (o - e) ** 2 / (e * (1 - e / n))
    df = groups - 2 if fitted_here else groups
    return float(stat), df, float(chi2.sf(stat, df))
