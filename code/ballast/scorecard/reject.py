"""Reject inference: what to do about the applicants with no outcome.

Mark II learned from booked loans. The applicants Fernhill declined,
and those it approved who walked away, have no outcome in Fernhill's
books, and a scorecard is used on all of them. Reject inference is the
family of methods that try to bring them into the sample:

- **ignore**: fit on the booked loans only (Mark II as it is);
- **reweight**: give each booked loan a weight of one over its chance
  of having been booked, so that the booked loans stand in for the
  applicants like them who were not;
- **hard cut-off**: score the unknowns with the booked-only model and
  call the riskiest of them bad, the rest good;
- **parcelling**: in each score band, call unknowns bad at random, at
  the booked loans' bad rate in that band (times an uplift);
- **fuzzy augmentation**: enter every unknown twice, as a bad with
  weight p and a good with weight 1 - p, p from the booked-only model;
- **bureau retro**: use what the bureau later saw of unknowns who
  borrowed elsewhere as their outcome.

Every method ends the same way: a training frame of rows, a bad flag
and a weight, refitted on Mark II's characteristics and bins (the bin
edges stay; the weights of evidence and coefficients are refitted).

    from ballast.scorecard import reject
    a = reject.applicants()                     # through the door
    base = reject.fit(train_rows, bad, weight)  # a Refit
    p = base.p_bad(rows)                        # predicted bad rate
    rows = reject.fuzzy(unknown, p, uplift=1.0)

This module never reads the truth database. Chapters that score the
methods against the truth pass the true outcomes in themselves.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

import fernhill
from ballast import data
from ballast.config import BALLAST, TODAY
from ballast.scorecard import model, points, sample
from ballast.scorecard.binning import Bins
from ballast.scorecard.sample import NO_FILE

# Fernhill's policy rules decline these applicants before any score is
# looked at; a scorecard is never asked to judge them.
POLICY_REASONS = ("recent_serious_arrears", "public_record",
                  "thin_file", "affordability")
UNKNOWN = ("declined", "not_taken_up")
OUTCOMES = ("booked",) + UNKNOWN
# Bands of Mark I's score minus the cut-off of the day, for the chance
# of being booked.
MARGIN_WIDTH = 10
RETRO_FROM, RETRO_TO = dt.date(2019, 1, 1), dt.date(2023, 12, 31)
METHODS = ("ignore", "reweight", "hard cut-off", "parcelling",
           "fuzzy", "bureau retro")
# Score bands for parcelling: 20 points, one doubling of the odds.
PARCEL_EDGES = [540, 560, 580, 600, 620, 640, 660]


# ------------------------------------------------------ who applied

def applicants(con=None, apps: pd.DataFrame | None = None,
               start: dt.date = sample.DEV_FROM,
               end: dt.date = sample.OOT_TO) -> pd.DataFrame:
    """Every personal-loan applicant who was booked, declined or
    walked away, with what Fernhill knows about their outcome.

    `bad` is the booked loan's outcome (NaN for the unknowns and the
    indeterminates); `split` is the booked loan's split in Mark II's
    sample, and for the unknowns a random 30% holdout drawn the same
    way; `policy` marks applicants declined by a policy rule.
    """
    con = con if con is not None else fernhill.connect()
    apps = apps if apps is not None else data.load_applications(con)
    s = sample.load_sample()
    mapping = s.attrs["bureau_map"]
    a = apps[(apps["product"] == sample.PRODUCT)
             & apps["outcome"].astype(str).isin(OUTCOMES)
             & (apps["app_date"] >= start)
             & (apps["app_date"] <= end)].reset_index(drop=True)
    out = pd.DataFrame({
        "app_id": a["app_id"].astype(str),
        "app_date": a["app_date"],
        "outcome": a["outcome"].astype(str),
        "decline_reason": a["decline_reason"].astype(object),
        "override": a["override"].astype(object),
        "mark1_score": a["mark1_score"].astype(float),
        "cutoff": a["cutoff"].astype(float),
    })
    out["margin"] = out["mark1_score"] - out["cutoff"]
    out["policy"] = out["decline_reason"].isin(POLICY_REASONS)
    out["period"] = sample.period(out["app_date"]).to_numpy()
    out["known"] = out["outcome"].eq("booked")
    chars = sample.characteristics(a, mapping)
    out = out.merge(chars, on="app_id", how="left", validate="1:1")
    out = model.with_file_flag(out)
    got = s[["app_id", "split", "outcome", "bad"]].rename(
        columns={"outcome": "loan_outcome"})
    out = out.merge(got, on="app_id", how="left", validate="1:1")
    out["bad"] = out["bad"].where(
        out["loan_outcome"].isin(["good", "bad"])).astype(float)
    # The unknowns: development years split 70/30 as the loans were.
    dev_unk = (out["period"] == "development") & ~out["known"]
    hold = sample.holdout(out.loc[dev_unk, "app_id"])
    out.loc[dev_unk, "split"] = np.where(hold, "holdout", "train")
    oot_unk = (out["period"] == "out_of_time") & ~out["known"]
    out.loc[oot_unk, "split"] = "out_of_time"
    return out.sort_values("app_id").reset_index(drop=True)


def retro(con=None) -> pd.DataFrame:
    """What the bureau later saw of applicants Fernhill did not lend
    to, 2019 to 2023: whether they opened a loan elsewhere within six
    months, and whether that loan went bad within twelve."""
    con = con if con is not None else fernhill.connect()
    r = con.execute("""
        SELECT app_id, opened_elsewhere, months_to_open,
               bad_12m_elsewhere
        FROM bureau_retro ORDER BY app_id""").df()
    r["bad_elsewhere"] = r["bad_12m_elsewhere"].astype(float)
    return r.drop(columns="bad_12m_elsewhere")


# ---------------------------------------------- chance of booking

def booking_rate(margin: pd.Series, booked: pd.Series,
                 width: float = MARGIN_WIDTH) -> pd.DataFrame:
    """Applicants, booked loans and the share booked, by band of Mark
    I's score minus the cut-off."""
    band = np.floor(margin / width) * width
    t = pd.DataFrame({"band": band, "booked": booked.astype(int)})
    g = t.groupby("band")["booked"].agg(["size", "sum"])
    g.columns = ["applicants", "booked"]
    g["rate"] = g["booked"] / g["applicants"]
    return g


def acceptance_weights(margin: pd.Series, booked: pd.Series,
                       width: float = MARGIN_WIDTH,
                       cap: float | None = None) -> pd.Series:
    """One over the chance of having been booked, for every row.

    The chance is the share booked among applicants in the same band
    of margin over the cut-off. Rows in a band where nobody was booked
    get NaN (there is no booked loan to stand in for them). `cap`
    limits the largest weight.
    """
    rate = booking_rate(margin, booked, width)["rate"]
    band = np.floor(margin / width) * width
    p = band.map(rate)
    w = 1 / p.where(p > 0)
    if cap is not None:
        w = w.clip(upper=cap)
    return w.rename("weight")


# ------------------------------------------------ inferring outcomes

def hard_cutoff(p_bad: pd.Series, uplift: float = 1.0) -> pd.Series:
    """Call the riskiest unknowns bad and the rest good.

    As many are called bad as the predicted rates add up to, times
    `uplift`: the riskiest round(uplift x sum(p)) rows, ties broken by
    position.
    """
    k = int(round(min(uplift * p_bad.sum(), len(p_bad))))
    order = np.argsort(-p_bad.to_numpy(), kind="stable")
    bad = np.zeros(len(p_bad), dtype=int)
    bad[order[:k]] = 1
    return pd.Series(bad, index=p_bad.index, name="bad")


def parcel(score: pd.Series, known_score: pd.Series,
           known_bad: pd.Series, edges: list[float],
           rng: np.random.Generator, uplift: float = 1.0) -> pd.Series:
    """In each score band, call unknowns bad at random, at the booked
    loans' bad rate in that band times `uplift` (at most 1)."""
    from ballast.scorecard.metrics import bands
    kb = pd.Series(np.asarray(known_bad, float))
    rate = kb.groupby(bands(known_score, edges).to_numpy(),
                      observed=False).mean()
    band = bands(score, edges).to_numpy()
    p = np.minimum(uplift * pd.Series(band).map(rate).astype(float)
                   .fillna(kb.mean()).to_numpy(), 1.0)
    return pd.Series((rng.random(len(score)) < p).astype(int),
                     index=score.index, name="bad")


def fuzzy(rows: pd.DataFrame, p_bad: pd.Series,
          uplift: float = 1.0) -> pd.DataFrame:
    """Every row twice: once bad with weight p, once good with 1 - p,
    p the predicted bad rate times `uplift` (at most 1)."""
    p = np.minimum(uplift * p_bad.to_numpy(), 1.0)
    bad = rows.assign(bad=1.0, weight=p)
    good = rows.assign(bad=0.0, weight=1 - p)
    return pd.concat([bad, good], ignore_index=True)


# ------------------------------------------------------ refitting

def weighted_woe(bins: Bins, x: pd.Series, bad: pd.Series,
                 weight: pd.Series) -> dict[str, float]:
    """Each bin's weight of evidence, counting each row by its weight.

    As in woe.woe_table: a zero weighted count of goods or bads is
    replaced by 0.5, and a bin with no rows at all gets 0.
    """
    idx = bins.index(x)
    k = len(bins.labels)
    w = np.asarray(weight, float)
    b = np.asarray(bad, float)
    n = np.bincount(idx, minlength=k)
    g = np.bincount(idx, weights=w * (1 - b), minlength=k)
    bb = np.bincount(idx, weights=w * b, minlength=k)
    G, B = g.sum(), bb.sum()
    gz = np.where(g > 0, g, 0.5)
    bz = np.where(bb > 0, bb, 0.5)
    woe = np.log((gz / G) / (bz / B))
    woe[n == 0] = 0.0
    return dict(zip(bins.labels, woe.astype(float)))


@dataclass
class Refit:
    """Mark II's characteristics and bin edges, with weights of
    evidence and coefficients refitted on a (weighted) sample."""
    coef: dict[str, float]
    bins: dict[str, Bins]
    n: float
    bad_share: float

    def log_odds(self, frame: pd.DataFrame) -> pd.Series:
        if model.FILE_FLAG in self.coef and model.FILE_FLAG not in frame:
            frame = model.with_file_flag(frame)
        lo = np.full(len(frame), self.coef["const"])
        for name, c in self.coef.items():
            if name == "const":
                continue
            b = self.bins[name]
            w = np.array([b.woe[lab] for lab in b.labels])
            lo = lo + c * w[b.index(frame[name])]
        return pd.Series(lo, index=frame.index, name="log_odds")

    def p_bad(self, frame: pd.DataFrame) -> pd.Series:
        """Predicted chance of going bad: 1 / (1 + odds good:bad)."""
        return (1 / (1 + np.exp(self.log_odds(frame)))).rename("p_bad")

    def score(self, frame: pd.DataFrame) -> pd.Series:
        """Points on Mark II's scale (600 at 50 to 1, 20 to double),
        unrounded."""
        return pd.Series(points.score_from_log_odds(
            self.log_odds(frame)), index=frame.index, name="score")

    def scorecard(self) -> points.Scorecard:
        return points.scorecard(self.coef, self.bins)


def mark2_bins() -> dict[str, Bins]:
    """Mark II's nine characteristics' bins, as Chapter 8 saved them."""
    return model.load_model()["binset"]


def fit(frame: pd.DataFrame, bad: pd.Series,
        weight: pd.Series | None = None,
        template: dict[str, Bins] | None = None,
        cols: list[str] = model.CHARACTERISTICS) -> Refit:
    """Refit Mark II's design on these rows.

    The bins' edges come from `template` (Mark II's by default). Each
    characteristic's WoE is measured on the weighted rows; "no file"
    is neutral (WoE 0) in every bureau line and carried by
    `bureau_file` alone, as in Mark II. Then a weighted logistic
    regression of good on the WoE-coded columns.
    """
    template = template if template is not None else mark2_bins()
    if model.FILE_FLAG in cols and model.FILE_FLAG not in frame:
        frame = model.with_file_flag(frame)
    bad = pd.Series(np.asarray(bad, float), index=frame.index)
    w = pd.Series(np.ones(len(frame)) if weight is None
                  else np.asarray(weight, float), index=frame.index)
    if w.isna().any() or bad.isna().any():
        raise ValueError("every row needs an outcome and a weight")
    bins = {}
    for name in cols:
        b = template[name]
        woe = weighted_woe(b, frame[name], bad, w)
        if b.missing == NO_FILE and name != model.FILE_FLAG:
            woe[NO_FILE] = 0.0
        bins[name] = replace(b, woe=woe)
    X = pd.DataFrame({n: np.array([bins[n].woe[lab]
                                   for lab in bins[n].labels])
                      [bins[n].index(frame[n])] for n in cols},
                     index=frame.index)
    design = sm.add_constant(X[cols], has_constant="add")
    r = sm.GLM((1 - bad).to_numpy(), design,
               family=sm.families.Binomial(),
               freq_weights=w.to_numpy()).fit()
    coef = {k: float(v) for k, v in r.params.items()}
    return Refit(coef, bins, float(w.sum()),
                 float((w * bad).sum() / w.sum()))


# ------------------------------------------- one training set per method

def training_set(method: str, accepts: pd.DataFrame,
                 unknown: pd.DataFrame, *, base: Refit | None = None,
                 retro_rows: pd.DataFrame | None = None,
                 rng: np.random.Generator | None = None,
                 uplift: float = 1.0, cap: float | None = None,
                 edges: list[float] = PARCEL_EDGES) -> pd.DataFrame:
    """The rows one method fits on, with `bad` and `weight` columns.

    `accepts` are booked loans with an outcome; `unknown` the declined
    and walked-away applicants of the same period. `base` is the model
    fitted on the accepts alone, which scores the unknowns for the
    methods that need it. `retro_rows` is `retro()`.
    """
    acc = accepts.assign(bad=accepts["bad"].astype(float), weight=1.0)
    if method == "ignore":
        return acc
    if method == "reweight":
        both = pd.concat([accepts, unknown])
        w = acceptance_weights(both["margin"], both["known"], cap=cap)
        return acc.assign(weight=w.loc[accepts.index].to_numpy())
    if method == "bureau retro":
        r = unknown.merge(retro_rows, on="app_id", how="inner")
        r = r[r["opened_elsewhere"].astype(bool)]
        r = r.assign(bad=r["bad_elsewhere"], weight=1.0)
        return pd.concat([acc, r], ignore_index=True)
    if base is None:
        raise ValueError(f"{method} needs the accepts-only model")
    p = base.p_bad(unknown)
    if method == "hard cut-off":
        inferred = unknown.assign(bad=hard_cutoff(p, uplift).to_numpy()
                                  .astype(float), weight=1.0)
    elif method == "parcelling":
        b = parcel(base.score(unknown), base.score(accepts),
                   accepts["bad"], edges, rng, uplift)
        inferred = unknown.assign(bad=b.to_numpy().astype(float),
                                  weight=1.0)
    elif method == "fuzzy":
        inferred = fuzzy(unknown, p, uplift)
    else:
        raise ValueError(f"unknown method {method!r}")
    return pd.concat([acc, inferred], ignore_index=True)


def frames(a: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The pieces every comparison uses, from `applicants()`: the
    scorecard's population only (policy declines are never scored).

    accepts   training loans with an outcome (Mark II's fit rows)
    unknown   declined and walked away, development, the 70% part
    holdout   everyone in the development 30% part
    oot       everyone out of time
    """
    sc = a[~a["policy"]]
    train = sc[sc["split"] == "train"]
    return {"accepts": train[train["known"] & train["bad"].notna()],
            "unknown": train[~train["known"]],
            "holdout": sc[sc["split"] == "holdout"],
            "oot": sc[sc["split"] == "out_of_time"]}


def fit_all(accepts: pd.DataFrame, unknown: pd.DataFrame,
            retro_rows: pd.DataFrame, rng: np.random.Generator,
            uplift: float = 1.0, methods=METHODS,
            cap: float | None = None, cols=model.CHARACTERISTICS,
            template: dict[str, Bins] | None = None
            ) -> dict[str, Refit]:
    """One refit per method, all on the same accepts and unknowns."""
    base = fit(accepts, accepts["bad"], cols=cols, template=template)
    out = {}
    for m in methods:
        if m == "ignore":
            out[m] = base
            continue
        t = training_set(m, accepts, unknown, base=base,
                         retro_rows=retro_rows, rng=rng,
                         uplift=uplift, cap=cap)
        out[m] = fit(t, t["bad"], t["weight"], cols=cols,
                     template=template)
    return out


# ----------------------------------------------------------- save

REJECT = BALLAST / "reject"


def save_refit(r: Refit, name: str, note: str = "",
               path: Path = REJECT) -> Path:
    """Write a refit (coefficients and bins) as JSON a person can read."""
    path.mkdir(parents=True, exist_ok=True)
    f = path / f"{name}.json"
    f.write_text(json.dumps({
        "name": name, "note": note, "fitted": str(TODAY),
        "rows_weighted": round(r.n, 4),
        "bad_share": round(r.bad_share, 6),
        "coefficients": {k: round(v, 6) for k, v in r.coef.items()},
        "bins": {k: b.to_dict() for k, b in r.bins.items()},
    }, indent=2) + "\n")
    return f


def load_refit(name: str, path: Path = REJECT) -> Refit:
    d = json.loads((path / f"{name}.json").read_text())
    return Refit(d["coefficients"],
                 {k: Bins.from_dict(v) for k, v in d["bins"].items()},
                 d["rows_weighted"], d["bad_share"])


# ------------------------------------------------------ comparing

def compare(p_bad: pd.Series, bad: pd.Series,
            group: pd.Series) -> dict[str, float]:
    """How a model's predictions stand against outcomes (whatever
    their source): Gini over all rows, and predicted against actual
    bad rate in each group."""
    from ballast.scorecard.metrics import gini
    p = np.asarray(p_bad, float)
    b = np.asarray(bad, float)
    out = {"gini": gini(-p, b.astype(int)),
           "predicted": float(p.mean()), "actual": float(b.mean())}
    g = np.asarray(group)
    for name in pd.unique(g):
        m = g == name
        out[f"{name}_predicted"] = float(p[m].mean())
        out[f"{name}_actual"] = float(b[m].mean())
    return out


def approve_best(p_bad: pd.Series, bad: pd.Series,
                 share: float) -> float:
    """The actual bad rate among the `share` of rows with the lowest
    predicted bad rate: what approving that many would have cost."""
    p = np.asarray(p_bad, float)
    b = np.asarray(bad, float)
    k = int(round(share * len(p)))
    order = np.argsort(p, kind="stable")[:k]
    return float(b[order].mean())
