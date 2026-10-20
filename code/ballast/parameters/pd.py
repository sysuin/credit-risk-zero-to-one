"""Probability of default, estimated properly.

Chapter 8 said a scorecard's scale is not a PD, and nothing in
Ballast would use it as one. This module builds the PD. Here a
**PD** is the chance that an account defaults, under the definition
Fernhill uses today (`dod2021`), within the twelve months after a
date, for every account open and not in default on that date,
whatever its age or arrears. An account that closes first has not
defaulted. The module has five parts:

- **calibration**: Mark II-R's score turned into the PD of a new
  personal loan's first year, by Platt's logistic or by isotonic
  regression, and PDs placed on Fernhill's master scale;
- **the cycle**: each product's yearly default rate, and the
  unemployment rate history and scenarios as a monthly path;
- **a 12-month PD model** for every open personal loan at a month
  end, from its score, its age, its arrears and, if asked, the
  unemployment rate over the year ahead (point in time); the same
  model at the decade's average unemployment is through the cycle;
- **term structures**: life tables, Kaplan-Meier and cumulative
  incidence curves, and a discrete-time hazard model by product,
  score band, months on book and unemployment;
- **low-default portfolios**: Pluto and Tasche's most prudent
  estimates, and a Bayesian fit of the master scale's shape.

    import fernhill
    from ballast.parameters import pd as pdm
    con = fernhill.connect()
    loans = pdm.personal_loans(con)
    cal = pdm.fit_calibration(loans.score, loans.d12)
    panel = pdm.account_months(con, loans)
    model = pdm.fit_pd_model(panel[panel.complete], macro=True)

This module never reads the truth database.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import beta, norm

from ballast import data
from ballast import performance as perf
from ballast.commercial.rating import MASTER_SCALE, grade_of
from ballast.config import AS_OF, BALLAST, ROOT
from ballast.decision import engine
from ballast.decision import policy as pol

DEFINITION = "dod2021"          # Fernhill's definition since 2021
HORIZON = 12                    # months: a PD is for the next year
# Calibration sample: personal loans opened after the growth push,
# old enough to have had their whole first year by AS_OF.
CALIBRATE_FROM = dt.date(2022, 7, 1)
CALIBRATE_TO = dt.date(2023, 12, 31)
LONG_RUN = (dt.date(2016, 1, 31), dt.date(2025, 12, 31))
SCORE_EDGES = {"personal": [560, 580, 600, 620],   # Mark II-R
               "card": [600, 630, 660],             # Mark I tiers
               "auto": [600, 630, 660],
               "mortgage": [600, 630, 660]}
MOB_EDGES = [0, 6, 12, 24, 36]              # the 12-month model
HAZARD_EDGES = [0, 3, 6, 9, 12, 18, 24, 36, 48, 60, 84]
CLOCK = {"sme_emergency": "due"}            # Chapter 6's due clock
PARAMS = BALLAST / "parameters"


# ------------------------------------------------------ calibration

def personal_loans(con) -> pd.DataFrame:
    """Every booked personal loan, scored by the champion, with its
    first default and whether it came in the first twelve months.

    `score` is Mark II-R's points for the application the loan came
    from; `d12` is 1 if the first default (dod2021) came within 12
    months on book; `seen12` says the twelve months have passed.
    """
    raw = data.load_applications(con, unknowns=False)
    apps = raw[raw["product"].astype(str).eq("personal")
               & raw["outcome"].astype(str).eq("booked")]
    card = engine.load_champion(pol.load_policy())
    score = card.score(engine.prepare(apps)).to_numpy()
    out = pd.DataFrame({"app_id": apps["app_id"].astype(str).to_numpy(),
                        "account_id": apps["account_id"].astype(str)
                        .to_numpy(), "score": score})
    acc = con.execute("""SELECT account_id, open_date FROM accounts
                         WHERE product = 'personal'""").df()
    out = out.merge(acc, on="account_id", validate="1:1")
    eps = perf.default_episodes(con, DEFINITION, products=["personal"])
    first = perf.first_defaults(eps)[["account_id", "default_month"]]
    out = out.merge(first, on="account_id", how="left")
    out["open_month"] = (pd.to_datetime(out["open_date"])
                         + pd.offsets.MonthEnd(0))
    out["default_month"] = pd.to_datetime(out["default_month"])
    mob = _months(out["open_month"], out["default_month"])
    out["d12"] = (mob <= HORIZON).astype(int)
    out["seen12"] = (out["open_month"] + pd.offsets.MonthEnd(HORIZON)
                     <= pd.Timestamp(AS_OF))
    return out.sort_values("account_id").reset_index(drop=True)


@dataclass
class Calibration:
    """A map from score to PD: Platt's logistic or isotonic steps."""
    method: str
    a: float = 0.0                  # platt: log odds = a + b * score
    b: float = 0.0
    x: list = field(default_factory=list)    # isotonic: steps
    y: list = field(default_factory=list)

    def pd(self, score) -> np.ndarray:
        s = np.asarray(score, dtype=float)
        if self.method == "platt":
            return 1 / (1 + np.exp(-(self.a + self.b * s)))
        return np.interp(s, self.x, self.y)

    def to_dict(self) -> dict:
        return asdict(self)


def fit_calibration(score, default, method: str = "platt"
                    ) -> Calibration:
    """Fit a score-to-PD map on loans whose outcome is known.

    Platt fits a logistic regression on the score alone: two
    numbers, a smooth curve. Isotonic fits the closest
    non-increasing step function: as many steps as the data want.
    """
    s = np.asarray(score, dtype=float)
    y = np.asarray(default, dtype=float)
    if method == "platt":
        r = sm.Logit(y, sm.add_constant(s)).fit(disp=0)
        return Calibration("platt", float(r.params[0]),
                           float(r.params[1]))
    if method != "isotonic":
        raise ValueError(f"unknown method {method!r}")
    from sklearn.isotonic import IsotonicRegression
    iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
    iso.fit(s, y)
    return Calibration("isotonic", x=iso.X_thresholds_.tolist(),
                       y=iso.y_thresholds_.tolist())


def log_loss(p, default) -> float:
    """Average surprise: -mean(y ln p + (1 - y) ln (1 - p))."""
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(default, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


RETAIL_POOLS = {1: "30", 2: "60"}   # accounts behind get a pool


def retail_grade(pd_, missed) -> np.ndarray:
    """Master-scale grade for an up-to-date account; a pool, "30"
    or "60", for one with one or two payments missed."""
    g = grade_of(pd_).astype(str)
    m = np.asarray(missed)
    return np.where(m == 1, "30", np.where(m == 2, "60", g))


# -------------------------------------------------------- the cycle

def annual_default_rates(con, episodes: pd.DataFrame, products,
                         years) -> pd.DataFrame:
    """Each product's default rate by year, Chapter 6's measure: of
    the accounts open and not in default on 1 January, the share
    with a new default during the year."""
    perf.prepare(con)
    eps = episodes.copy()
    eps["dm"] = pd.to_datetime(eps["default_month"])
    eps["cm"] = pd.to_datetime(eps["cure_month"])
    rows = []
    for year in years:
        jan1 = pd.Timestamp(year - 1, 12, 31)
        open_ = con.execute(f"""
            SELECT DISTINCT root_id AS account_id, product
            FROM history WHERE month = ?
              AND status IN {perf.OPEN}""", [jan1.date()]).df()
        in_d = eps[(eps.dm <= jan1)
                   & (eps.cm.isna() | (eps.cm > jan1))]
        risk = open_[~open_.account_id.isin(in_d.account_id)]
        new = eps[eps.dm.dt.year == year]
        hit = risk.account_id.isin(new.account_id)
        for p in products:
            sel = risk["product"] == p
            rows.append({"year": year, "product": p,
                         "at_risk": int(sel.sum()),
                         "defaults": int((hit & sel).sum())})
    out = pd.DataFrame(rows)
    out["rate"] = out["defaults"] / out["at_risk"].replace(0, np.nan)
    return out


def unemployment(con, scenario: str = "base") -> pd.Series:
    """Monthly unemployment: history to AS_OF, then one of the
    scenarios published for the AS_OF reporting date."""
    h = con.execute("""SELECT month, unemployment_pct FROM macro
                       ORDER BY month""").df()
    s = con.execute("""SELECT month, unemployment_pct FROM scenarios
                       WHERE as_of = ? AND scenario = ?
                       ORDER BY month""", [AS_OF, scenario]).df()
    u = pd.concat([h, s[pd.to_datetime(s.month)
                        > pd.Timestamp(AS_OF)]])
    return pd.Series(u.unemployment_pct.to_numpy(),
                     index=pd.to_datetime(u.month), name="u")


def ahead(u: pd.Series, months: int = HORIZON) -> pd.Series:
    """The average of the next `months` months, for each month."""
    return (u[::-1].rolling(months).mean()[::-1].shift(-1)
            .rename("u_ahead"))


def long_run_unemployment(con) -> float:
    """The decade's average unemployment: the through-the-cycle
    economy."""
    u = unemployment(con)
    lo, hi = (pd.Timestamp(d) for d in LONG_RUN)
    return float(u[(u.index >= lo) & (u.index <= hi)].mean())


# ------------------------------------------------ the 12-month model

def account_months(con, loans: pd.DataFrame, every: int = 3,
                   scenario: str = "base") -> pd.DataFrame:
    """Every personal loan at every `every`-th month end while it is
    open, not in default and at most two payments behind.

    `y` is 1 if a new default starts in the next twelve months;
    `complete` says those months have passed; `u_ahead` is the
    average unemployment over them (the scenario after AS_OF).
    """
    h = con.execute("""
        SELECT account_id, month, missed, status
        FROM performance WHERE product = 'personal'
        ORDER BY account_id, month""").df()
    h["month"] = pd.to_datetime(h["month"])
    h = h[(h.month.dt.month % every == 0)
          & h.status.isin(["up_to_date", "arrears"])]
    h = h.merge(loans[["account_id", "score", "open_month"]],
                on="account_id")
    eps = perf.default_episodes(con, DEFINITION, products=["personal"])
    e = eps[["account_id", "default_month", "cure_month"]].copy()
    e["dm"] = pd.to_datetime(e.default_month)
    e["cm"] = pd.to_datetime(e.cure_month)
    m = h[["account_id", "month"]].reset_index().merge(
        e[["account_id", "dm", "cm"]], on="account_id", how="left")
    end = m.month + pd.offsets.MonthEnd(HORIZON)
    m["in_default"] = (m.dm <= m.month) & (m.cm.isna()
                                           | (m.cm > m.month))
    m["y"] = (m.dm > m.month) & (m.dm <= end)
    g = m.groupby("index")[["in_default", "y"]].any()
    h["in_default"] = g["in_default"].to_numpy()
    h["y"] = g["y"].to_numpy().astype(int)
    h["mob"] = _months(h.open_month, h.month)
    h = h[~h.in_default & (h.missed <= 2) & (h.mob >= 1)]
    u = ahead(unemployment(con, scenario))
    h["u_ahead"] = h.month.map(u)
    h["complete"] = (h.month + pd.offsets.MonthEnd(HORIZON)
                     <= pd.Timestamp(AS_OF))
    cols = ["account_id", "month", "mob", "missed", "score",
            "u_ahead", "y", "complete"]
    return h[cols].sort_values(["account_id", "month"]
                               ).reset_index(drop=True)


def mob_group(mob) -> pd.Categorical:
    labels = ["1-6", "7-12", "13-24", "25-36", "37+"]
    return pd.cut(np.asarray(mob), MOB_EDGES + [10_000],
                  labels=labels)


@dataclass
class PDModel:
    """Logistic regression for default within twelve months."""
    params: dict
    bse: dict
    macro: bool

    def design(self, frame: pd.DataFrame, u_ahead=None) -> pd.DataFrame:
        g = mob_group(frame["mob"])
        X = pd.DataFrame({"const": 1.0,
                          "score": frame["score"].astype(float),
                          "missed_1": (frame["missed"] == 1) * 1.0,
                          "missed_2": (frame["missed"] == 2) * 1.0},
                         index=frame.index)
        for lab in g.categories[1:]:
            X[f"mob_{lab}"] = (g == lab) * 1.0
        if self.macro:
            u = frame["u_ahead"] if u_ahead is None else u_ahead
            X["u_ahead"] = np.broadcast_to(np.asarray(u, dtype=float),
                                           len(frame))
        return X

    def pd(self, frame: pd.DataFrame, u_ahead=None) -> pd.Series:
        """Point in time with the frame's own `u_ahead`; through the
        cycle with `u_ahead` set to the long-run average."""
        X = self.design(frame, u_ahead)
        z = X[list(self.params)].to_numpy() @ np.array(
            list(self.params.values()))
        return pd.Series(1 / (1 + np.exp(-z)), index=frame.index)

    def to_dict(self) -> dict:
        return asdict(self)


def fit_pd_model(panel: pd.DataFrame, macro: bool = True) -> PDModel:
    """Fit the 12-month model on rows whose year has passed."""
    if (~panel["complete"]).any():
        raise ValueError("fit only on rows with a complete year")
    X = PDModel({}, {}, macro).design(panel)
    r = sm.Logit(panel["y"].astype(float), X).fit(disp=0)
    return PDModel({k: float(v) for k, v in r.params.items()},
                   {k: float(v) for k, v in r.bse.items()}, macro)


# -------------------------------------------------- term structures

def band(score, edges) -> np.ndarray:
    """Score bands such as '<560', '560-579', ..., '620+'."""
    s = np.asarray(score, dtype=float)
    labels = ([f"<{edges[0]}"]
              + [f"{a}-{b - 1}" for a, b in zip(edges, edges[1:])]
              + [f"{edges[-1]}+"])
    idx = np.searchsorted(edges, s, side="right")
    return np.array(labels, dtype=object)[idx]


def durations(con, product: str) -> pd.DataFrame:
    """One row per account (a migrated card is one account) with the
    months from the start of its clock to its first default, its
    closure or AS_OF, whichever came first.

    `event` is 1 for a default, 2 for a closure (repaid, prepaid or
    closed by the customer) and 0 for still open, not in default, at
    AS_OF (censored). `band` is the champion's score band at
    application, or "all" for products without one.
    """
    perf.prepare(con)
    acc = con.execute("""
        WITH chain AS (
            SELECT r.root_id AS account_id,
                   any_value(r.root_open) AS open_date,
                   max(a.close_date) FILTER (
                       WHERE a.close_reason <> 'migrated') AS closed,
                   any_value(a.app_id) FILTER (
                       WHERE a.account_id = r.root_id) AS app_id
            FROM account_root r JOIN accounts a USING (account_id)
            WHERE r.product = ? GROUP BY 1),
        due AS (SELECT root_id AS account_id,
                       any_value(first_due) AS first_due
                FROM history WHERE product = ? GROUP BY 1)
        SELECT c.*, d.first_due, ap.mark1_score
        FROM chain c LEFT JOIN due d USING (account_id)
        LEFT JOIN applications ap USING (app_id)
        ORDER BY account_id""", [product, product]).df()
    start = pd.to_datetime(acc.open_date) + pd.offsets.MonthEnd(0)
    if CLOCK.get(product) == "due":
        due = pd.to_datetime(acc.first_due) - pd.offsets.MonthEnd(1)
        start = due.fillna(start)
    eps = perf.default_episodes(con, DEFINITION, products=[product])
    first = perf.first_defaults(eps)[["account_id", "default_month"]]
    acc = acc.merge(first, on="account_id", how="left")
    t_d = _months(start, pd.to_datetime(acc.default_month))
    closed = pd.to_datetime(acc.closed) + pd.offsets.MonthEnd(0)
    t_c = _months(start, closed)
    t_e = _months(start, pd.Series(pd.Timestamp(AS_OF),
                                   index=acc.index))
    t = np.fmin(np.fmin(np.nan_to_num(t_d, nan=1e9),
                        np.nan_to_num(t_c, nan=1e9)), t_e)
    event = np.where(~np.isnan(t_d) & (t_d <= t), 1,
                     np.where(~np.isnan(t_c) & (t_c <= t), 2, 0))
    if product == "personal":
        loans = personal_loans(con)[["account_id", "score"]]
        score = acc[["account_id"]].merge(loans, how="left")["score"]
    else:
        score = acc["mark1_score"]
    edges = SCORE_EDGES.get(product)
    out = pd.DataFrame({
        "account_id": acc.account_id, "product": product,
        "start": start, "score": score.to_numpy(dtype=float),
        "band": band(score, edges) if edges else "all",
        "t": t.astype(int), "event": event})
    return out[out.t >= 1].reset_index(drop=True)


def life_table(d: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """At risk, defaults and closures at each month on the clock."""
    t, ev = d["t"].to_numpy(), d["event"].to_numpy()
    rows = []
    for k in range(1, horizon + 1):
        n = int((t >= k).sum())
        rows.append((k, n, int(((t == k) & (ev == 1)).sum()),
                     int(((t == k) & (ev == 2)).sum())))
    return pd.DataFrame(rows, columns=["month", "at_risk", "defaults",
                                       "closed"]).set_index("month")


def kaplan_meier(table: pd.DataFrame) -> pd.Series:
    """Cumulative PD with closures treated as censored: the PD of a
    loan that could not close."""
    n = table["at_risk"].replace(0, np.nan)
    h = (table["defaults"] / n).fillna(0)
    return (1 - (1 - h).cumprod()).rename("kaplan_meier")


def cumulative_incidence(table: pd.DataFrame) -> pd.Series:
    """Cumulative PD with closure as a competing exit: the share of
    loans that default before they close (Aalen-Johansen)."""
    n = table["at_risk"].replace(0, np.nan)
    h_d = (table["defaults"] / n).fillna(0)
    h_all = ((table["defaults"] + table["closed"]) / n).fillna(0)
    alive = (1 - h_all).cumprod().shift(1, fill_value=1.0)
    return (alive * h_d).cumsum().rename("cumulative_incidence")


def person_months(d: pd.DataFrame, u: pd.Series) -> pd.DataFrame:
    """Accounts at risk, defaults and closures by band, month on the
    clock and calendar month, with that month's unemployment."""
    rep = d.loc[d.index.repeat(d["t"].to_numpy())]
    k = rep.groupby(level=0).cumcount().to_numpy() + 1
    month = (rep["start"].dt.to_period("M") + k).dt.to_timestamp("M")
    last = rep["t"].to_numpy() == k
    pm = pd.DataFrame({"band": rep["band"].to_numpy(), "mob": k,
                       "month": month.to_numpy(),
                       "d": (last & (rep.event.to_numpy() == 1)) * 1,
                       "c": (last & (rep.event.to_numpy() == 2)) * 1})
    agg = pm.groupby(["band", "mob", "month"]).agg(
        n=("d", "size"), d=("d", "sum"), c=("c", "sum")).reset_index()
    agg["u"] = agg["month"].map(u).to_numpy()
    return agg


@dataclass
class HazardModel:
    """Monthly hazards of default and of closure, by months on the
    clock, score band and (for default) the month's unemployment."""
    product: str
    bands: list
    groups: list                    # hazard groups present, by index
    default: dict                   # coefficients of the default fit
    close: dict                     # coefficients of the closure fit
    u_bse: float = 0.0

    def _X(self, mob, band_, u=None, with_u=True) -> np.ndarray:
        mob = np.atleast_1d(np.asarray(mob))
        gi = _hazard_group(mob)
        gi = np.minimum(gi, max(self.groups))
        cols = [np.ones(len(mob))]
        cols += [(gi == g) * 1.0 for g in self.groups[1:]]
        b = np.broadcast_to(np.asarray(band_, dtype=object), len(mob))
        cols += [(b == x) * 1.0 for x in self.bands[1:]]
        if with_u:
            cols.append(np.broadcast_to(np.asarray(u, dtype=float),
                                        len(mob)))
        return np.column_stack(cols)

    def hazard(self, mob, band_, u) -> np.ndarray:
        coef = np.array(list(self.default.values()))
        z = self._X(mob, band_, u) @ coef
        return 1 / (1 + np.exp(-z))

    def exit_hazard(self, mob, band_) -> np.ndarray:
        z = self._X(mob, band_, with_u=False) @ np.array(
            list(self.close.values()))
        return 1 / (1 + np.exp(-z))

    def term_structure(self, band_, u_path, start: int = 0
                       ) -> pd.DataFrame:
        """Month by month from month `start` on the clock: hazards,
        the chance of reaching each month, the marginal PD and the
        cumulative PD, with closure as a competing exit."""
        u_path = np.asarray(u_path, dtype=float)
        mob = start + np.arange(1, len(u_path) + 1)
        h = self.hazard(mob, band_, u_path)
        x = self.exit_hazard(mob, band_)
        alive = np.cumprod(np.r_[1.0, 1 - h - x])[:-1]
        marginal = alive * h
        return pd.DataFrame({"month": mob - start, "mob": mob,
                             "hazard": h, "exit": x,
                             "survival": alive,
                             "marginal_pd": marginal,
                             "cumulative_pd": marginal.cumsum()})

    def to_dict(self) -> dict:
        return asdict(self)


def _hazard_group(mob) -> np.ndarray:
    return np.searchsorted(HAZARD_EDGES, np.asarray(mob), side="left"
                           ) - 1


def fit_hazard(product: str, pm: pd.DataFrame) -> HazardModel:
    """Fit the default and closure hazards on person-month counts
    (binomial regressions on the aggregated cells)."""
    gi = _hazard_group(pm["mob"].to_numpy())
    groups = sorted(set(gi.tolist()))
    bands = sorted(pm["band"].unique().tolist(), key=_band_key)
    model = HazardModel(product, bands, groups, {}, {})
    X = model._X(pm["mob"], pm["band"], pm["u"])
    names = (["const"] + [f"mob_g{g}" for g in groups[1:]]
             + [f"band_{b}" for b in bands[1:]] + ["u"])
    fam = sm.families.Binomial()
    yd = np.column_stack([pm.d, pm.n - pm.d])
    rd = sm.GLM(yd, X, family=fam).fit()
    yc = np.column_stack([pm.c, pm.n - pm.c])
    rc = sm.GLM(yc, X[:, :-1], family=fam).fit()
    model.default = dict(zip(names, map(float, rd.params)))
    model.close = dict(zip(names[:-1], map(float, rc.params)))
    model.u_bse = float(rd.bse[-1])
    return model


def _band_key(b: str):
    if b == "all":
        return 0
    return int(b.lstrip("<").split("-")[0].rstrip("+")) + (
        0 if b.startswith("<") else 1)


# -------------------------------------------- low-default portfolios

def pluto_tasche(n, d, confidence: float = 0.9, rho: float = 0.0,
                 years: int = 1, sims: int = 4000, seed: int = 0
                 ) -> np.ndarray:
    """Most prudent PD for each grade, best grade first.

    Grade k's estimate is the largest PD, shared by grades k and
    worse, that would still give the defaults seen there or fewer
    with probability 1 - `confidence`. With `rho` > 0 defaults move
    together through one factor per year (Vasicek), across `years`
    years with the obligors spread evenly over them.
    """
    n, d = np.asarray(n, dtype=int), np.asarray(d, dtype=int)
    out = []
    for k in range(len(n)):
        N, D = int(n[k:].sum()), int(d[k:].sum())
        if rho == 0:
            out.append(float(beta.ppf(confidence, D + 1, N - D)))
            continue
        z = np.random.default_rng(seed).standard_normal((sims, years))
        size = np.full(years, N // years)
        size[: N % years] += 1
        lo, hi = 1e-7, 0.999
        for _ in range(50):
            p = (lo + hi) / 2
            cond = norm.cdf((norm.ppf(p) - np.sqrt(rho) * z)
                            / np.sqrt(1 - rho))
            if _prob_at_most(D, size, cond) > 1 - confidence:
                lo = p
            else:
                hi = p
        out.append((lo + hi) / 2)
    return np.array(out)


def _prob_at_most(D, size, cond) -> float:
    """Average over factor draws of P(total defaults <= D)."""
    from scipy.stats import binom
    pmf = np.zeros((cond.shape[0], D + 1))
    pmf[:, 0] = 1.0
    ks = np.arange(D + 1)
    for j, m in enumerate(size):
        b = binom.pmf(ks[None, :], m, cond[:, [j]])
        new = np.zeros_like(pmf)
        for i in range(D + 1):
            new[:, i:] += pmf[:, [i]] * b[:, : D + 1 - i]
        pmf = new
    return float(pmf.sum(axis=1).mean())


def bayes_scale(n, d, grades, slope=(np.log(2), 0.25)) -> pd.DataFrame:
    """A Bayesian fit of log odds of default = a + b x grade.

    The prior says each grade's odds are about twice the one before
    (the master scale's shape: b near ln 2, sd 0.25) and nothing
    about the level a. The defaults decide the level and adjust the
    slope. Computed exactly on a grid; returns each grade's
    posterior mean PD and its 5% and 95% points.
    """
    n, d = np.asarray(n, float), np.asarray(d, float)
    g = np.asarray(grades, float)
    A = np.linspace(-14, 0, 701)[:, None, None]
    B = np.linspace(0.05, 1.6, 311)[None, :, None]
    p = 1 / (1 + np.exp(-(A + B * g)))
    ll = (d * np.log(p) + (n - d) * np.log1p(-p)).sum(axis=2)
    ll += norm.logpdf(B[..., 0], slope[0], slope[1])
    w = np.exp(ll - ll.max())
    w /= w.sum()
    rows = []
    for j, grade in enumerate(g):
        pj = p[..., j].ravel()
        order = np.argsort(pj)
        cw = np.cumsum(w.ravel()[order])
        lo, hi = np.searchsorted(cw, [0.05, 0.95])
        rows.append({"grade": int(grade),
                     "mean": float((w * p[..., j]).sum()),
                     "lower": float(pj[order][lo]),
                     "upper": float(pj[order][hi])})
    post_b = float((w * B[..., 0]).sum())
    out = pd.DataFrame(rows).set_index("grade")
    out.attrs["slope"] = post_b
    return out


# ------------------------------------------------------------ saving

def save_json(name: str, obj) -> str:
    """Write one parameter file under data/ballast/parameters/."""
    PARAMS.mkdir(parents=True, exist_ok=True)
    path = PARAMS / name
    path.write_text(json.dumps(obj, indent=1, default=float) + "\n")
    return str(path.relative_to(ROOT))


def load_json(name: str):
    return json.loads((PARAMS / name).read_text())


def load_calibration() -> Calibration:
    return Calibration(**load_json("pd_calibration.json"))


def load_pd_model() -> PDModel:
    d = load_json("pd_model.json")
    return PDModel(d["params"], d["bse"], d["macro"])


def load_hazards() -> dict[str, HazardModel]:
    return {k: HazardModel(**v) for k, v in
            load_json("pd_hazard.json")["models"].items()}


def _months(a, b) -> np.ndarray:
    """Whole calendar months from a to b (NaN where b is missing)."""
    a, b = pd.to_datetime(a), pd.to_datetime(b)
    out = ((b.dt.year - a.dt.year) * 12
           + (b.dt.month - a.dt.month)).to_numpy(dtype=float)
    return out


MASTER = MASTER_SCALE           # the bank's one scale, Chapter 16's
