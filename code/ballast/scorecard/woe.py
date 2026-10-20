"""Weight of evidence and information value, and applying them.

For each bin of a characteristic, the **weight of evidence** (WoE)
compares the bin's share of all the goods with its share of all the
bads:

    WoE = ln( share of goods in the bin / share of bads in the bin )

Positive means the bin holds more than its share of goods (safer than
average), negative more than its share of bads. The **information
value** (IV) adds up, over the bins, how far apart the two shares are,
weighted by the WoE, and says how well the characteristic separates
goods from bads on its own.

A bin with no goods or no bads would have an infinite WoE, so a count
of zero is replaced by 0.5 in that bin, and only there.

    from ballast.scorecard import woe
    table = woe.woe_table(bins, x, bad)   # the characteristic report
    woe.fit(bins, x, bad)                      # stores WoE in bins.woe
    coded = woe.encode(frame, binset)          # WoE-coded columns
    binset, iv = woe.fit_binset(frame, bad, spec)   # all at once
    woe.save_binset(binset, path); woe.load_binset(path)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ballast.scorecard.binning import Bins, bin_all, counts


def woe_table(bins: Bins, x: pd.Series, bad: pd.Series) -> pd.DataFrame:
    """The characteristic report: counts, bad rate, WoE, IV by bin."""
    t = counts(bins, x, bad)
    t["goods"] = t["n"] - t["bads"]
    G, B = t["goods"].sum(), t["bads"].sum()
    g = t["goods"].astype(float).where(t["goods"] > 0, 0.5)
    b = t["bads"].astype(float).where(t["bads"] > 0, 0.5)
    t["share"] = t["n"] / t["n"].sum()
    t["bad_rate"] = t["bads"] / t["n"].where(t["n"] > 0)
    t["pct_good"] = g / G
    t["pct_bad"] = b / B
    t["woe"] = np.log(t["pct_good"] / t["pct_bad"])
    t["iv"] = (t["pct_good"] - t["pct_bad"]) * t["woe"]
    empty = t["n"] == 0                  # a bin nobody fell in: neutral
    t.loc[empty, ["woe", "iv"]] = 0.0
    return t[["bin", "n", "share", "goods", "bads", "bad_rate",
              "pct_good", "pct_bad", "woe", "iv"]]


def information_value(bins: Bins, x: pd.Series,
                      bad: pd.Series) -> float:
    return float(woe_table(bins, x, bad)["iv"].sum())


def fit(bins: Bins, x: pd.Series, bad: pd.Series) -> Bins:
    """Store each bin's WoE, measured on these rows, in `bins.woe`."""
    t = woe_table(bins, x, bad)
    bins.woe = dict(zip(t["bin"], t["woe"].astype(float)))
    return bins


def transform(bins: Bins, x: pd.Series) -> pd.Series:
    """Replace each value by its bin's WoE."""
    if not bins.woe:
        raise ValueError(f"{bins.name}: fit the WoE first")
    w = np.array([bins.woe[label] for label in bins.labels])
    return pd.Series(w[bins.index(x)], index=x.index, name=bins.name)


def encode(frame: pd.DataFrame,
           binset: dict[str, Bins]) -> pd.DataFrame:
    """WoE-code every characteristic in `binset`, one column each."""
    return pd.DataFrame({name: transform(b, frame[name])
                         for name, b in binset.items()},
                        index=frame.index)


def fit_binset(frame: pd.DataFrame, bad: pd.Series,
               spec: dict[str, dict]
               ) -> tuple[dict[str, Bins], dict[str, float]]:
    """Coarse-class every characteristic in `spec`, fit its WoE, and
    measure its IV, all on the same rows."""
    binset = bin_all(frame, bad, spec)
    iv = {}
    for name, b in binset.items():
        fit(b, frame[name], bad)
        iv[name] = information_value(b, frame[name], bad)
    return binset, iv


def save_binset(binset: dict[str, Bins], path: Path,
                iv: dict[str, float] | None = None) -> Path:
    """Write the bins (and their WoE) as JSON a person can read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {name: b.to_dict() | ({"iv": round(iv[name], 6)}
                                if iv and name in iv else {})
           for name, b in binset.items()}
    path.write_text(json.dumps(out, indent=2) + "\n")
    return path


def load_binset(path: Path) -> dict[str, Bins]:
    d = json.loads(Path(path).read_text())
    return {name: Bins.from_dict(v) for name, v in d.items()}
