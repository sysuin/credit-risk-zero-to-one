"""Binning a characteristic: fine classes first, then coarse ones.

A scorecard gives points to ranges of a characteristic, not to each
value, so every characteristic is cut into bins. The cutting happens
twice. **Fine classing** cuts it into many small bins (twenty, or one
per value when there are fewer) so the analyst can see how the bad
rate moves. **Coarse classing** merges neighbouring fine classes until
every bin is big enough to trust and the bad rate moves in one
direction only. A missing value is never a number: it gets a bin of
its own, labelled with what it means ("no file", "not employed").

    from ballast.scorecard import binning
    fine = binning.fine_classes("age", x, bad)
    bins = binning.coarse_classes(fine, x, bad, trend="decreasing")
    bins.assign(x)              # each value's bin label
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import erfc

import numpy as np
import pandas as pd

MAX_FINE = 20
MIN_SHARE = 0.05        # every ordinary bin holds 5% of the rows
MAX_BINS = 8
ALPHA = 0.10            # neighbours must differ at this significance


@dataclass
class Bins:
    """How one characteristic is cut. Fitted once, applied to anything.

    numeric:      `edges` are the cut points; a bin holds values from
                  one edge (included) up to the next (excluded), and
                  the end bins are open.
    categorical:  `groups` lists the categories in each bin.
    `missing` is the label of the bin for missing values, if any.
    `woe` (filled by woe.fit) maps each label to its weight of
    evidence.
    """
    name: str
    kind: str
    edges: list[float] = field(default_factory=list)
    groups: list[list[str]] = field(default_factory=list)
    missing: str | None = None
    integer: bool = False
    woe: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------- labels
    def _num_label(self, i: int) -> str:
        e, fmt = self.edges, self._fmt
        if not e:
            return "all"
        if i == 0:
            return f"<{fmt(e[0])}"
        if i == len(e):
            return f"{fmt(e[-1])}+"
        hi = e[i] - 1 if self.integer else e[i]
        return f"{fmt(e[i - 1])}-{fmt(hi)}"

    def _fmt(self, v: float) -> str:
        if self.integer:
            return f"{int(v):,}"
        return f"{v:,.4g}" if abs(v) < 1000 else f"{v:,.0f}"

    @property
    def labels(self) -> list[str]:
        """Ordinary bins in order, then the missing bin."""
        if self.kind == "numeric":
            k = len(self.edges) + 1
            out = [self._num_label(i) for i in range(k)]
        else:
            out = ["/".join(g) for g in self.groups]
        return out + ([self.missing] if self.missing else [])

    # ------------------------------------------------------- assign
    def index(self, x: pd.Series) -> np.ndarray:
        """Each value's bin number; the missing bin is the last."""
        miss = x.isna().to_numpy()
        n_ord = len(self.labels) - (1 if self.missing else 0)
        if self.kind == "numeric":
            v = x.astype("float64").to_numpy()
            idx = np.searchsorted(np.asarray(self.edges, float),
                                  np.where(miss, 0, v), side="right")
        else:
            where = {c: i for i, g in enumerate(self.groups) for c in g}
            vals = x.astype(object).where(~miss, None)
            unseen = sorted({v for v in vals[~miss] if v not in where})
            if unseen:
                raise ValueError(
                    f"{self.name}: categories the bins never saw: "
                    f"{unseen}")
            idx = np.array([where.get(v, 0) for v in vals])
        if miss.any():
            if not self.missing:
                raise ValueError(
                    f"{self.name}: missing values and no bin for them")
            idx = np.where(miss, n_ord, idx)
        return idx.astype(int)

    def assign(self, x: pd.Series) -> pd.Series:
        """Each value's bin label, as an ordered categorical."""
        labels = self.labels
        return pd.Series(pd.Categorical.from_codes(
            self.index(x), categories=labels, ordered=True),
            index=x.index, name=self.name)

    # ---------------------------------------------------- serialise
    def to_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind,
                "edges": [float(e) for e in self.edges],
                "groups": self.groups, "missing": self.missing,
                "integer": self.integer, "labels": self.labels,
                "woe": {k: round(float(v), 6)
                        for k, v in self.woe.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> Bins:
        return cls(d["name"], d["kind"], list(d["edges"]),
                   [list(g) for g in d["groups"]], d["missing"],
                   d["integer"], dict(d.get("woe", {})))


# ------------------------------------------------------------ counting

def counts(bins: Bins, x: pd.Series, bad: pd.Series) -> pd.DataFrame:
    """Rows and bads in each bin, missing bin last."""
    idx = bins.index(x)
    k = len(bins.labels)
    b = np.asarray(bad, dtype=int)
    n = np.bincount(idx, minlength=k)
    nb = np.bincount(idx, weights=b, minlength=k).astype(int)
    return pd.DataFrame({"bin": bins.labels, "n": n, "bads": nb})


def _is_integer(v: np.ndarray) -> bool:
    return bool(np.all(v == np.round(v)))


# ------------------------------------------------------- fine classing

def fine_classes(name: str, x: pd.Series, bad: pd.Series | None = None,
                 *, kind: str | None = None, missing: str | None = None,
                 max_fine: int = MAX_FINE,
                 decimals: int | None = None) -> Bins:
    """Many small bins: one per value, or about `max_fine` equal ones.

    Numeric characteristics are cut at quantiles of the values seen;
    categorical ones get one bin per category, ordered by bad rate when
    `bad` is given. Missing values go to the bin labelled `missing`.
    """
    present = x.dropna()
    if kind is None:
        kind = ("numeric" if pd.api.types.is_numeric_dtype(x)
                else "categorical")
    if x.isna().any() and missing is None:
        missing = "missing"
    if kind == "categorical":
        cats = sorted(present.astype(str).unique())
        if bad is not None:
            rate = pd.Series(np.asarray(bad, float), index=x.index)[
                x.notna()].groupby(present.astype(str)).mean()
            cats = sorted(cats, key=lambda c: (rate[c], c))
        return Bins(name, kind, groups=[[c] for c in cats],
                    missing=missing)
    v = present.astype("float64").to_numpy()
    integer = _is_integer(v)
    values = np.unique(v)
    if len(values) <= max_fine:
        edges = values[1:]
    else:
        qs = np.arange(1, max_fine) / max_fine
        edges = np.quantile(v, qs, method="higher")
        if decimals is not None:
            edges = np.round(edges, decimals)
        edges = np.unique(edges)
        edges = edges[edges > values[0]]
    return Bins(name, kind, edges=[float(e) for e in edges],
                missing=missing, integer=integer)


# ----------------------------------------------------- coarse classing

def _merge(edges: list, groups: list, i: int, kind: str) -> None:
    """Merge ordinary bin i with bin i + 1, in place."""
    if kind == "numeric":
        del edges[i]
    else:
        groups[i] = groups[i] + groups[i + 1]
        del groups[i + 1]


def _iv_terms(n: np.ndarray, b: np.ndarray, G: float, B: float):
    g = n - b
    pg = np.maximum(g, 0.5) / G
    pb = np.maximum(b, 0.5) / B
    return (pg - pb) * np.log(pg / pb)


def trend_of(n: np.ndarray, b: np.ndarray) -> str:
    """Whether the bad rate mostly rises or falls across the bins."""
    keep = n > 0
    rate = b[keep] / n[keep]
    pos = np.arange(len(n))[keep]
    if len(rate) < 2:
        return "decreasing"
    c = np.cov(pos, rate, aweights=n[keep])[0, 1]
    return "increasing" if c > 0 else "decreasing"


def p_value(n1: float, b1: float, n2: float, b2: float) -> float:
    """Chance of bad rates this far apart if two bins were really one.

    The two-proportion test: the difference in bad rates divided by
    its standard error under the pooled rate, against a normal curve.
    """
    pooled = (b1 + b2) / (n1 + n2)
    se = np.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = abs(b1 / n1 - b2 / n2) / se
    return float(erfc(z / np.sqrt(2)))


def coarse_classes(fine: Bins, x: pd.Series, bad: pd.Series, *,
                   trend: str = "auto", min_share: float = MIN_SHARE,
                   alpha: float | None = ALPHA,
                   max_bins: int = MAX_BINS) -> Bins:
    """Merge neighbouring fine classes into a few bins worth trusting.

    1. Small bins: while any ordinary bin holds less than `min_share`
       of the rows with a value, merge the smallest with whichever
       neighbour has the closer bad rate.
    2. One direction: `trend` is "increasing" or "decreasing" (the bad
       rate as the characteristic rises), "auto" to take the data's
       overall direction, or "none" for no constraint. While two
       neighbours break it, merge the pair whose bad rates are closest.
    3. Different enough: while two neighbours' bad rates could be the
       same at significance `alpha`, merge the most alike pair.
    4. At most `max_bins`: merge the neighbours whose merging loses
       the least information value.
    The missing bin is never merged with anything. Categorical bins
    are first put in order of bad rate, so step 2 has nothing to do.
    """
    kind = fine.kind
    edges, groups = list(fine.edges), [list(g) for g in fine.groups]
    c = counts(fine, x, bad)
    ordinary = c.iloc[: len(c) - (1 if fine.missing else 0)]
    n = ordinary["n"].to_numpy(float)
    b = ordinary["bads"].to_numpy(float)
    if kind == "categorical":
        order = np.lexsort((np.arange(len(n)),
                            b / np.maximum(n, 1)))
        groups = [groups[i] for i in order]
        n, b = n[order], b[order]
    total, B = n.sum(), max(c["bads"].sum(), 1)
    G = max(c["n"].sum() - c["bads"].sum(), 1)

    def merge(i):
        nonlocal n, b
        _merge(edges, groups, i, kind)
        n = np.concatenate([n[:i], [n[i] + n[i + 1]], n[i + 2:]])
        b = np.concatenate([b[:i], [b[i] + b[i + 1]], b[i + 2:]])

    def rate():
        return b / np.maximum(n, 1)

    # 1. every bin big enough
    while len(n) > 1 and (n / total).min() < min_share:
        i = int(np.argmin(n))
        r = rate()
        if i == 0:
            j = 0
        elif i == len(n) - 1:
            j = i - 1
        else:
            j = i - 1 if abs(r[i] - r[i - 1]) <= abs(r[i] - r[i + 1]) \
                else i
        merge(j)

    # 2. the bad rate moves one way
    if trend == "auto":
        trend = trend_of(n, b)
    if trend != "none" and kind == "numeric":
        sign = 1 if trend == "increasing" else -1
        while len(n) > 1:
            d = np.diff(rate()) * sign
            broken = np.flatnonzero(d < 0)
            if not len(broken):
                break
            merge(int(broken[np.argmin(np.abs(d[broken]))]))

    # 3. neighbours that differ
    while alpha is not None and len(n) > 1:
        p = [p_value(n[i], b[i], n[i + 1], b[i + 1])
             for i in range(len(n) - 1)]
        if max(p) <= alpha:
            break
        merge(int(np.argmax(p)))

    # 4. not too many bins
    while len(n) > max_bins:
        base = _iv_terms(n, b, G, B)
        loss = []
        for i in range(len(n) - 1):
            m = _iv_terms(np.array([n[i] + n[i + 1]]),
                          np.array([b[i] + b[i + 1]]), G, B)[0]
            loss.append(base[i] + base[i + 1] - m)
        merge(int(np.argmin(loss)))

    return Bins(fine.name, kind, edges=edges, groups=groups,
                missing=fine.missing, integer=fine.integer)


def is_monotone(bins: Bins, x: pd.Series, bad: pd.Series) -> bool:
    """True if the ordinary bins' bad rates never change direction."""
    c = counts(bins, x, bad)
    c = c.iloc[: len(c) - (1 if bins.missing else 0)]
    r = np.diff(c["bads"] / c["n"].clip(lower=1))
    return bool((r >= 0).all() or (r <= 0).all())


def turns(bins: Bins, x: pd.Series, bad: pd.Series) -> int:
    """How many times the bad rate changes direction across the bins."""
    c = counts(bins, x, bad)
    c = c.iloc[: len(c) - (1 if bins.missing else 0)]
    s = np.sign(np.diff(c["bads"] / c["n"].clip(lower=1)))
    s = s[s != 0]
    return int((np.diff(s) != 0).sum())


# ------------------------------------------------------ many at once

def bin_characteristic(name: str, x: pd.Series, bad: pd.Series,
                       spec: dict | None = None) -> tuple[Bins, Bins]:
    """Fine and coarse classes for one characteristic, by its spec.

    `spec` may give kind, missing (the label for missing values),
    trend and decimals (to round fine cut points: -1 for tens).
    """
    spec = spec or {}
    fine = fine_classes(name, x, bad, kind=spec.get("kind"),
                        missing=spec.get("missing"),
                        decimals=spec.get("decimals"))
    coarse = coarse_classes(fine, x, bad,
                            trend=spec.get("trend", "auto"))
    return fine, coarse


def bin_all(frame: pd.DataFrame, bad: pd.Series,
            spec: dict[str, dict]) -> dict[str, Bins]:
    """Coarse classes for every characteristic named in `spec`."""
    return {name: bin_characteristic(name, frame[name], bad, s)[1]
            for name, s in spec.items()}
