"""Monitoring: is the book, and the models deciding it, still what we
think they are?

A model is fitted once and used for years. Monitoring is the habit of
checking, every month, the things that would tell you it has stopped
being right before the losses do. This module holds four kinds of
check:

- **stability**: whether the people being scored still look like the
  people the model was built on (the population stability index, a
  characteristic analysis, a mean-shift test, and a noise level for
  each, so that an alarm means something);
- **performance**: early reads of arrears by vintage, the Gini and
  the calibration by period, with intervals;
- **early warning**: a behavioural score for existing personal loans
  and cards from each account's own history, and signals for business
  clients, with a watchlist whose record can be measured;
- **the pack**: the monthly report, as text that fits a page.

    from ballast import monitoring as mon
    mon.psi(reference, actual)              # one number
    mon.monthly_stability(values, months)   # month by month
    mon.characteristic_analysis(ref_lines, now_lines)
    mon.early_reads(con, "personal")        # vintages by quarter
    mon.stress_indicators(con, start, end)  # the 2020 dashboard
    f = mon.behaviour_frame(con, months)    # account x quarter end
    b = mon.fit_behaviour(f[dev], "card")   # a points table
    p = mon.business_panel(con)             # company x month end
    mon.watch_record(p, mon.watch(p))       # hit rate, false alarms
    print(mon.pack(con))                    # December 2025

Nothing here decides. Every function reads, measures and reports; the
decision engine, the scorecards and the rating model are left as their
chapters built them.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from ballast import market as mk
from ballast import performance as perf
from ballast.config import AS_OF, BALLAST, SEED
from ballast.scorecard import metrics
from ballast.scorecard import points as pts

MONITORING = BALLAST / "monitoring"

# --------------------------------------------------- the thresholds

# The industry's rules of thumb for a population stability index:
# below 0.10 nothing to see, 0.10 to 0.25 look into it, above 0.25
# act. They ignore how many applicants a month you have, so every
# PSI here is also set against its own noise level (NOISE_LEVEL).
PSI_AMBER = 0.10
PSI_RED = 0.25
NOISE_LEVEL = 0.99        # the PSI that chance alone exceeds 1% of the time
Z_ALARM = 3.0             # a mean score moved by three standard errors
BINS = 10                 # deciles of the reference
FLOOR = 1e-4              # an empty band counts as 0.01%


def light(value: float, amber: float, red: float) -> str:
    """'red', 'amber' or 'green' for a value against two limits."""
    if value >= red:
        return "red"
    return "amber" if value >= amber else "green"


# --------------------------------------------- population stability

def decile_edges(reference, bins: int = BINS) -> np.ndarray:
    """Band edges at the reference's quantiles, open at both ends.
    Tied scores can merge bands, so there may be fewer than `bins`."""
    r = np.asarray(reference, dtype=float)
    q = np.unique(np.quantile(r, np.linspace(0, 1, bins + 1)))
    return np.r_[-np.inf, q[1:-1], np.inf]


def shares(values, edges) -> np.ndarray:
    """The share of `values` in each band."""
    v = np.asarray(values, dtype=float)
    return np.histogram(v, edges)[0] / max(len(v), 1)


def psi_from_shares(expected, actual) -> float:
    """Sum over bands of (actual - expected) x ln(actual / expected),
    with empty bands floored at FLOOR."""
    e = np.maximum(np.asarray(expected, dtype=float), FLOOR)
    a = np.maximum(np.asarray(actual, dtype=float), FLOOR)
    return float(((a - e) * np.log(a / e)).sum())


def psi(reference, actual, edges=None, bins: int = BINS) -> float:
    """The population stability index of `actual` against `reference`
    over the reference's deciles (or the `edges` given)."""
    edges = decile_edges(reference, bins) if edges is None else edges
    return psi_from_shares(shares(reference, edges),
                           shares(actual, edges))


def psi_table(reference, actual, edges=None, bins: int = BINS,
              whole: bool = True) -> pd.DataFrame:
    """Band by band: the shares and each band's part of the PSI. With
    `whole` (scores are integers) a band is labelled lowest-highest."""
    edges = decile_edges(reference, bins) if edges is None else edges
    e, a = shares(reference, edges), shares(actual, edges)
    top = 1 if whole else 0
    lo = ["" if np.isinf(x) else f"{x:g}" for x in edges[:-1]]
    hi = ["" if np.isinf(x) else f"{x - top:g}" for x in edges[1:]]
    band = [f"{x}-{y}" if x and y else
            (f"<= {y}" if y else f">= {x}") for x, y in zip(lo, hi)]
    ef, af = np.maximum(e, FLOOR), np.maximum(a, FLOOR)
    return pd.DataFrame({"band": band, "reference": e, "actual": a,
                         "part": (af - ef) * np.log(af / ef)})


def category_psi(reference, actual) -> float:
    """PSI over the categories (or points values) a line takes."""
    r, a = pd.Series(reference), pd.Series(actual)
    cats = sorted(set(r.dropna()) | set(a.dropna()))
    e = r.value_counts(normalize=True).reindex(cats, fill_value=0)
    x = a.value_counts(normalize=True).reindex(cats, fill_value=0)
    return psi_from_shares(e.to_numpy(), x.to_numpy())


def psi_noise(n_actual: int, n_reference: int, bands: int = BINS,
              level: float = NOISE_LEVEL) -> float:
    """The PSI that sampling alone exceeds with probability 1 - level
    when nothing has changed. For small differences the PSI times
    n_actual x n_reference / (n_actual + n_reference) is close to a
    chi-square on bands - 1 degrees of freedom."""
    n_eff = 1 / (1 / n_actual + 1 / n_reference)
    return float(stats.chi2.ppf(level, bands - 1) / n_eff)


def mean_shift_z(reference, actual) -> float:
    """How many standard errors the mean has moved."""
    r = np.asarray(reference, dtype=float)
    a = np.asarray(actual, dtype=float)
    se = np.sqrt(r.var(ddof=1) / len(a) + r.var(ddof=1) / len(r))
    return float((a.mean() - r.mean()) / se)


def monthly_stability(values, months, reference=None,
                      window: int = 12, bins: int = BINS
                      ) -> pd.DataFrame:
    """For each month: applicants, mean, PSI, its noise level and the
    mean shift, against either a fixed `reference` (a boolean mask
    over the rows) or, when `reference` is None, the `window` months
    before. `months` is a period or month-start date per row."""
    v = pd.Series(np.asarray(values, dtype=float))
    m = pd.Series(pd.PeriodIndex(months, freq="M"))
    rows = []
    for month in sorted(m.unique()):
        now = v[m == month]
        if reference is None:
            ref = v[(m < month) & (m >= month - window)]
            if (m < month - window + 1).sum() == 0:
                continue                 # not a full window behind it
        else:
            ref = v[np.asarray(reference, dtype=bool)]
        edges = decile_edges(ref, bins)
        rows.append({
            "month": str(month), "n": len(now),
            "mean": now.mean(), "shift": now.mean() - ref.mean(),
            "psi": psi(ref, now, edges),
            "noise": psi_noise(len(now), len(ref), len(edges) - 1),
            "z": mean_shift_z(ref, now)})
    return pd.DataFrame(rows)


def characteristic_analysis(reference: pd.DataFrame,
                            actual: pd.DataFrame) -> pd.DataFrame:
    """For each line of a points scorecard: the PSI over the points
    the line awards, and how far the line's average points moved.
    The shifts add up to the change in the mean score."""
    rows = []
    for line in reference.columns:
        r, a = reference[line], actual[line]
        rows.append({"line": line, "psi": category_psi(r, a),
                     "reference": r.mean(), "actual": a.mean(),
                     "shift": a.mean() - r.mean()})
    return pd.DataFrame(rows).sort_values("psi", ascending=False,
                                          ignore_index=True)


# ------------------------------------------------------ performance

EARLY_SQL = """
WITH h AS (
    SELECT root_id, product, root_open,
           date_diff('month', root_open, month) AS mob, missed, status
    FROM history WHERE product = ?)
SELECT root_id, any_value(root_open) AS root_open,
       max(mob) AS seen,
       max(CASE WHEN mob <= 3 AND missed >= 1 THEN 1 ELSE 0 END) AS e3,
       max(CASE WHEN mob <= 6 AND missed >= 1 THEN 1 ELSE 0 END) AS e6,
       max(CASE WHEN mob <= 6 AND missed >= 2 THEN 1 ELSE 0 END) AS e6_60,
       max(CASE WHEN mob <= 12 AND missed >= 3 THEN 1 ELSE 0 END) AS b12,
       max(CASE WHEN mob <= 24 AND missed >= 3 THEN 1 ELSE 0 END) AS b24
FROM h GROUP BY root_id ORDER BY root_id
"""
READS = {"e3": 3, "e6": 6, "e6_60": 6, "b12": 12, "b24": 24}
READ_TEXT = {"e3": "30+ by month 3", "e6": "30+ by month 6",
             "e6_60": "60+ by month 6", "b12": "90+ by month 12",
             "b24": "90+ by month 24"}


def early_accounts(con, product: str = "personal") -> pd.DataFrame:
    """One row per loan (migrated cards stitched to their first
    number): opening date, months seen, and each early-read flag."""
    perf.prepare(con)
    return con.execute(EARLY_SQL, [product]).df()


def early_reads(con, product: str = "personal", as_of: dt.date = AS_OF,
                freq: str = "Q") -> pd.DataFrame:
    """Vintages by quarter of opening (or half-year, `freq="H"`): loans
    and the share of them reaching each early-read marker. A cell is
    NaN until every loan in the vintage has been on the book that many
    months."""
    a = early_accounts(con, product)
    opened = pd.to_datetime(a["root_open"])
    if freq == "H":
        half = np.where(opened.dt.month <= 6, "H1", "H2")
        a["vintage"] = opened.dt.year.astype(str) + half
    else:
        a["vintage"] = opened.dt.to_period(freq).astype(str)
    last = opened.groupby(a["vintage"]).max()
    end = pd.Timestamp(as_of)
    out = a.groupby("vintage").agg(loans=("root_id", "size"),
                                   **{k: (k, "mean") for k in READS})
    for k, mob in READS.items():
        young = (last + pd.DateOffset(months=mob)) > end
        out.loc[young[young].index, k] = np.nan
    return out.reset_index()


def binomial_interval(bads: int, n: int, level: float = 0.95
                      ) -> tuple[float, float]:
    """Clopper-Pearson interval for a rate seen as bads out of n."""
    a = (1 - level) / 2
    lo = stats.beta.ppf(a, bads, n - bads + 1) if bads else 0.0
    hi = stats.beta.ppf(1 - a, bads + 1, n - bads) if bads < n else 1.0
    return float(lo), float(hi)


def calibration_drift(promised, bad, period) -> pd.DataFrame:
    """For each period: loans, bads, the rate promised and seen, their
    ratio, the seen rate's 95% interval and whether the promise lies
    outside it."""
    t = pd.DataFrame({"p": np.asarray(promised, dtype=float),
                      "y": np.asarray(bad, dtype=int),
                      "period": np.asarray(period)})
    rows = []
    for k, g in t.groupby("period", sort=True):
        n, b = len(g), int(g["y"].sum())
        lo, hi = binomial_interval(b, n)
        p = g["p"].mean()
        rows.append({"period": k, "n": n, "bads": b, "promised": p,
                     "seen": b / n, "ratio": (b / n) / p, "lo": lo,
                     "hi": hi, "outside": not lo <= p <= hi})
    return pd.DataFrame(rows)


def gini_drift(score, bad, period, n: int = 500,
               seed: int = SEED) -> pd.DataFrame:
    """The Gini in each period with a bootstrap 95% interval."""
    t = pd.DataFrame({"s": np.asarray(score, dtype=float),
                      "y": np.asarray(bad, dtype=int),
                      "period": np.asarray(period)})
    rng = np.random.default_rng(seed)
    rows = []
    for k, g in t.groupby("period", sort=True):
        d = metrics.bootstrap(metrics.gini, g["s"], g["y"], n=n,
                              rng=rng)
        lo, hi = metrics.interval(d)
        rows.append({"period": k, "n": len(g), "bads": int(g["y"].sum()),
                     "gini": metrics.gini(g["s"], g["y"]),
                     "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


# ----------------------------------------- stress when arrears lie

STRESS_SQL = """
WITH book AS (
    SELECT p.*, h.account_id IS NOT NULL AS holiday_account
    FROM performance p
    LEFT JOIN (SELECT DISTINCT account_id FROM account_events
               WHERE event = 'payment_holiday_start') h
      USING (account_id)
    WHERE p.product IN ('personal', 'card', 'auto', 'mortgage')
      AND p.status IN ('up_to_date', 'arrears', 'default')
      AND p.month BETWEEN ? AND ?),
apps AS (
    SELECT last_day(app_date) AS month, count(*) AS applications,
           avg(enquiries_6m) AS enquiries,
           avg(CASE WHEN enquiries_6m >= 3 THEN 1 ELSE 0 END) AS enq3
    FROM applications
    WHERE bureau_hit AND product IN ('personal', 'card', 'auto')
    GROUP BY 1),
asks AS (
    SELECT last_day(event_date) AS month, count(*) AS holiday_requests
    FROM account_events WHERE event = 'payment_holiday_start'
    GROUP BY 1)
SELECT b.month, count(*) AS accounts,
       avg(CASE WHEN missed >= 1 THEN 1 ELSE 0 END) AS dq30,
       avg(CASE WHEN missed >= 1 THEN 1.0 ELSE 0.0 END)
         FILTER (WHERE holiday_account) AS dq30_holiday_accounts,
       avg(CASE WHEN missed >= 1 THEN 1.0 ELSE 0.0 END)
         FILTER (WHERE NOT holiday_account) AS dq30_others,
       avg(payment_holiday::INT) AS on_holiday,
       avg(CASE WHEN missed >= 1 OR payment_holiday THEN 1 ELSE 0 END)
           AS not_paying,
       sum(balance_cents) FILTER (WHERE product = 'card')
         / sum(limit_cents) FILTER (WHERE product = 'card')
           AS card_utilisation,
       avg(CASE WHEN paid_cents <= 1.05 * scheduled_cents THEN 1.0
                ELSE 0.0 END)
         FILTER (WHERE product = 'card' AND scheduled_cents > 0)
           AS card_minimum_only,
       any_value(coalesce(k.holiday_requests, 0)) AS holiday_requests,
       any_value(a.applications) AS applications,
       any_value(a.enquiries) AS enquiries,
       any_value(a.enq3) AS enquiries_3plus,
       any_value(m.unemployment_pct) AS unemployment
FROM book b
LEFT JOIN asks k USING (month)
LEFT JOIN apps a USING (month)
LEFT JOIN macro m USING (month)
GROUP BY b.month ORDER BY b.month
"""


def stress_indicators(con, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Consumer book, month by month: arrears (all, and split by
    whether the account ever had a payment holiday), the share on
    holiday, the share not paying as agreed (behind or on holiday),
    card utilisation and minimum-only payers, holiday requests,
    applicants' bureau enquiries, and unemployment."""
    return con.execute(STRESS_SQL, [start, end]).df()


# ------------------------------------------------ behavioural score

BEHAVIOUR_SQL = """
WITH obs AS (
    SELECT h.root_id, h.account_id, h.product, h.month,
           date_diff('month', h.root_open, h.month) AS mob,
           h.missed, h.balance_cents, h.limit_cents, r.amount_cents
    FROM history h
    JOIN account_root r ON r.account_id = h.root_id
    WHERE h.product IN ({products})
      AND h.month IN ({months})
      AND h.status IN ('up_to_date', 'arrears') AND h.missed <= 2
      AND NOT h.payment_holiday),
past AS (
    SELECT o.root_id, o.month,
           sum(CASE WHEN p.missed > 0 THEN 1 ELSE 0 END) AS behind_12m,
           max(p.missed) FILTER (WHERE p.month > o.month
                                 - INTERVAL 6 MONTH) AS worst_6m,
           sum(p.paid_cents) FILTER (WHERE p.month > o.month
                                     - INTERVAL 3 MONTH) AS paid_3m,
           sum(p.balance_cents) FILTER (WHERE p.month > o.month
                                        - INTERVAL 3 MONTH) AS bal_3m
    FROM obs o JOIN history p
      ON p.root_id = o.root_id AND p.month <= o.month
     AND p.month > o.month - INTERVAL 12 MONTH
    GROUP BY ALL),
future AS (
    SELECT o.root_id, o.month, count(*) AS months_after,
           max(CASE WHEN f.missed >= 3
                     OR f.status IN ('default', 'charged_off')
                    THEN 1 ELSE 0 END) AS bad
    FROM obs o JOIN history f
      ON f.root_id = o.root_id AND f.month > o.month
     AND f.month <= o.month + INTERVAL 12 MONTH
    GROUP BY ALL)
SELECT o.*, a.mark1_score AS application_score, past.behind_12m,
       past.worst_6m, past.paid_3m, past.bal_3m,
       coalesce(future.bad, 0) AS bad
FROM obs o
JOIN past USING (root_id, month)
LEFT JOIN future USING (root_id, month)
JOIN accounts ac ON ac.account_id = o.root_id
JOIN applications a ON a.app_id = ac.app_id
ORDER BY o.month, o.root_id
"""


def quarter_ends(start: dt.date, end: dt.date) -> list[dt.date]:
    """Every quarter end from `start` to `end`."""
    return [d.date() for d in pd.date_range(start, end, freq="QE")]


def behaviour_frame(con, months, products=("personal", "card"),
                    as_of: dt.date = AS_OF) -> pd.DataFrame:
    """One row per account (stitched across the card migration) per
    observation month, for accounts open, not in default, at most two
    payments behind and not on a payment holiday that month.

    months_on_book  since the first account in the chain opened
    missed_now      payments behind at the month end (0, 1, 2)
    behind_12m      month ends behind in the last twelve
    utilisation     cards: balance / limit; personal loans: balance
                    left / amount lent
    payment_ratio   cards: paid over the last three statements /
                    their balances (1 = paid in full); NaN for loans
    application_score  Mark I's score when the account was opened
    bad             90+ days, default or charge-off within 12 months
    complete        the 12 months after the observation have passed
    """
    perf.prepare(con)
    ms = ", ".join(f"DATE '{m}'" for m in months)
    ps = ", ".join(f"'{p}'" for p in products)
    f = con.execute(BEHAVIOUR_SQL.format(products=ps, months=ms)).df()
    card = f["product"].eq("card")
    bal = f["balance_cents"].astype(float)
    f["months_on_book"] = f.pop("mob")
    f["missed_now"] = f.pop("missed")
    f["utilisation"] = np.where(
        card, bal / f["limit_cents"].astype(float),
        bal / f["amount_cents"].astype(float))
    b3 = f["bal_3m"].astype(float)
    f["payment_ratio"] = np.where(
        card & (b3 > 0), f["paid_3m"].astype(float) / b3.where(b3 > 0),
        np.where(card, 1.0, np.nan))
    month = pd.to_datetime(f["month"])
    f["complete"] = month + pd.DateOffset(months=12) <= pd.Timestamp(
        as_of)
    f.loc[~f["complete"], "bad"] = np.nan
    return f.drop(columns=["paid_3m", "bal_3m", "worst_6m"])


# Each line: the column it reads, the band edges (a value at an edge
# goes into the band above it), and the band labels.
BEHAVIOUR_LINES = {
    "months_on_book": ("months_on_book", [7, 13, 25, 37],
                       ["1-6", "7-12", "13-24", "25-36", "37+"]),
    "missed_now": ("missed_now", [1, 2], ["0", "1", "2"]),
    "behind_12m": ("behind_12m", [1], ["none", "1+"]),
    "utilisation": ("utilisation", [0.1, 0.3, 0.5, 0.7, 0.9],
                    ["<10%", "10-30%", "30-50%", "50-70%", "70-90%",
                     "90%+"]),
    "balance_left": ("utilisation", [0.25, 0.5, 0.75],
                     ["<25%", "25-50%", "50-75%", "75%+"]),
    "payment_ratio": ("payment_ratio", [0.04, 0.1, 0.5, 0.99],
                      ["minimum", "4-10%", "10-50%", "50-99%", "in full"]),
    "application": ("application_score", [560, 590, 620, 650],
                    ["<560", "560-589", "590-619", "620-649", "650+"]),
}
PRODUCT_LINES = {
    "card": ["months_on_book", "missed_now", "utilisation"],
    "personal": ["months_on_book", "missed_now", "behind_12m",
                 "balance_left"],
}


def behaviour_bins(frame: pd.DataFrame, lines) -> pd.DataFrame:
    """The band each row falls in, line by line."""
    out = {}
    for line in lines:
        col, edges, labels = BEHAVIOUR_LINES[line]
        x = frame[col].astype(float).to_numpy()
        i = np.searchsorted(edges, x, side="right")
        out[line] = pd.Categorical(np.asarray(labels)[i],
                                   categories=labels)
    return pd.DataFrame(out, index=frame.index)


@dataclass
class BehaviourScore:
    """A points table on Mark II's scale (600 points = odds of 50 to 1
    good, 20 points double the odds), one per product. `table` maps
    line -> band -> points; the riskiest band of each line scores 0."""
    product: str
    base: int
    table: dict

    @property
    def lines(self) -> list[str]:
        return list(self.table)

    def line_points(self, frame: pd.DataFrame) -> pd.DataFrame:
        b = behaviour_bins(frame, self.lines)
        return pd.DataFrame({ln: b[ln].astype(str).map(self.table[ln])
                             for ln in self.lines}, index=frame.index)

    def score(self, frame: pd.DataFrame) -> pd.Series:
        return (self.base + self.line_points(frame).sum(axis=1)).astype(
            int).rename("behaviour_score")

    def bad_rate(self, frame: pd.DataFrame) -> pd.Series:
        """The 12-month bad rate the scale promises at each score."""
        return pd.Series(pts.bad_rate_at(self.score(frame)),
                         index=frame.index)

    def to_dict(self) -> dict:
        return {"product": self.product, "base": self.base,
                "table": self.table}


def fit_behaviour(frame: pd.DataFrame, product: str,
                  application: bool = True,
                  lines=None) -> BehaviourScore:
    """Fit a behavioural score for one product on rows with a known
    outcome: a logistic regression of `bad` on each line's bands
    (dummy-coded against the first band), turned into points. `lines`
    replaces the product's own list (PRODUCT_LINES)."""
    lines = list(lines or PRODUCT_LINES[product]) + (
        ["application"] if application else [])
    f = frame[frame["product"].eq(product) & frame["bad"].notna()]
    b = behaviour_bins(f, lines)
    X = pd.get_dummies(b, prefix_sep="=", drop_first=True).astype(float)
    r = sm.Logit(f["bad"].astype(float), sm.add_constant(X)).fit(
        disp=0, maxiter=200)
    table, base = {}, pts.OFFSET - pts.FACTOR * r.params["const"]
    for line in lines:
        labels = BEHAVIOUR_LINES[line][2]
        raw = {lab: -pts.FACTOR * r.params.get(f"{line}={lab}", 0.0)
               for lab in labels}
        low = min(raw.values())
        table[line] = {lab: int(round(v - low)) for lab, v in raw.items()}
        base += low
    return BehaviourScore(product, int(round(base)), table)


def save_behaviour(scores: list[BehaviourScore],
                   path: Path = MONITORING) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    out = path / "behaviour.json"
    out.write_text(json.dumps({s.product: s.to_dict() for s in scores},
                              indent=1) + "\n")
    return out


def load_behaviour(path: Path = MONITORING) -> dict[str, BehaviourScore]:
    d = json.loads((path / "behaviour.json").read_text())
    return {k: BehaviourScore(v["product"], v["base"], v["table"])
            for k, v in d.items()}


# ---------------------------------------- business early warning

PANEL_SQL = """
SELECT f.company_id, m.month,
       sum(m.drawn_cents) FILTER (WHERE f.kind = 'revolver')
           AS revolver_drawn,
       sum(m.limit_cents) FILTER (WHERE f.kind = 'revolver')
           AS revolver_limit,
       sum(m.drawn_cents) AS drawn,
       min(f.covenant_max_leverage) AS covenant_leverage,
       max(f.covenant_min_interest_cover) AS covenant_cover
FROM facility_months m JOIN facilities f USING (facility_id)
WHERE m.status = 'performing'
GROUP BY ALL ORDER BY f.company_id, m.month
"""
HORIZON = 12              # months: a flag is a hit if default follows


def business_panel(con, start: dt.date = dt.date(2017, 3, 31),
                   end: dt.date = AS_OF,
                   as_of: dt.date = AS_OF) -> pd.DataFrame:
    """Company x month end for commercial clients with a performing
    facility, up to the month before any default, with the signals an
    early-warning watchlist reads:

    revolver_use   drawn / limit across the company's revolvers
    use_at_review  the same at the last annual review
    leverage, cover   debt / EBITDA and EBITDA / interest from the
                   latest accounts Fernhill held (arrive 31 March)
    covenant_leverage, covenant_cover   the tightest covenant set
    grade, model_grade, held   from the last annual review
    months_since_review
    dd             distance to default (listed clients only)
    default_12m    a default within HORIZON months (NaN if unknown)
    """
    p = con.execute(PANEL_SQL).df()
    p["month"] = pd.to_datetime(p["month"]).astype("datetime64[ns]")
    p = p[(p["month"] >= pd.Timestamp(start))
          & (p["month"] <= pd.Timestamp(end))]
    fin = con.execute("""
        SELECT company_id, fiscal_year, ebitda_cents, total_debt_cents,
               interest_cents FROM financials""").df()
    fin["arrive"] = pd.to_datetime([mk.arrives(int(y))
                                    for y in fin["fiscal_year"]]
                                   ).astype("datetime64[ns]")
    p = pd.merge_asof(p.sort_values("month"),
                      fin.sort_values("arrive"), left_on="month",
                      right_on="arrive", by="company_id")
    e = p["ebitda_cents"].astype(float)
    p["leverage"] = np.where(e > 0, p["total_debt_cents"] / e, np.inf)
    i = p["interest_cents"].astype(float)
    p["cover"] = np.where(i > 0, e / i, np.inf)
    p["revolver_use"] = (p["revolver_drawn"].astype(float)
                         / p["revolver_limit"].astype(float))
    r = con.execute("""
        SELECT company_id, rating_date, internal_grade AS grade,
               model_grade, analyst_override AS held
        FROM ratings WHERE internal_grade IS NOT NULL""").df()
    r["rating_date"] = pd.to_datetime(r["rating_date"]).astype(
        "datetime64[ns]")
    p = pd.merge_asof(p.sort_values("month"),
                      r.sort_values("rating_date"), left_on="month",
                      right_on="rating_date", by="company_id")
    p["months_since_review"] = (
        (p["month"].dt.year - p["rating_date"].dt.year) * 12
        + p["month"].dt.month - p["rating_date"].dt.month)
    at = p.loc[p["month"] == p["rating_date"],
               ["company_id", "rating_date", "revolver_use"]]
    p = p.merge(at.rename(columns={"revolver_use": "use_at_review"}),
                on=["company_id", "rating_date"], how="left")
    dd = mk.merton_panel(con)[["company_id", "month", "dd"]].copy()
    dd["month"] = pd.to_datetime(dd["month"]).astype("datetime64[ns]")
    p = p.merge(dd, on=["company_id", "month"], how="left")
    d = con.execute("SELECT company_id, default_month "
                    "FROM corporate_defaults").df()
    d["default_month"] = pd.to_datetime(d["default_month"]).astype(
        "datetime64[ns]")
    p = p.merge(d, on="company_id", how="left")
    p = p[~(p["default_month"] <= p["month"])]
    ahead = p["month"] + pd.DateOffset(months=HORIZON)
    p["default_12m"] = ((p["default_month"] > p["month"])
                        & (p["default_month"] <= ahead)).astype(float)
    p.loc[ahead > pd.Timestamp(as_of), "default_12m"] = np.nan
    keep = ["company_id", "month", "drawn", "revolver_use",
            "use_at_review", "leverage", "cover", "covenant_leverage",
            "covenant_cover", "grade", "model_grade", "held",
            "months_since_review", "dd", "default_month", "default_12m"]
    return p[keep].sort_values(["company_id", "month"],
                               ignore_index=True)


# Each trigger: what it looks for, and the test on the panel. A
# missing signal (no revolver, not listed) never fires.
TRIGGERS = {
    "revolver_75": ("revolvers 75% or more drawn",
                    lambda p: p["revolver_use"] >= 0.75),
    "revolver_up": ("revolver use up 15 points since the review",
                    lambda p: p["revolver_use"] - p["use_at_review"]
                    >= 0.15),
    "covenants": ("leverage and cover both outside covenant",
                  lambda p: (p["leverage"] > p["covenant_leverage"])
                  & (p["cover"] < p["covenant_cover"])),
    "market": ("distance to default below 1.5, grade 6 or better",
               lambda p: (p["dd"] < 1.5) & (p["grade"] <= 6)),
    "held": ("grade held 2+ notches better than the model",
             lambda p: p["model_grade"] - p["grade"] >= 2),
    "grade_8": ("internal grade 8 or worse",
                lambda p: p["grade"] >= 8),
}
WATCHLIST = ("revolver_75", "revolver_up", "market")


def watch(panel: pd.DataFrame, triggers=tuple(TRIGGERS)) -> pd.DataFrame:
    """One boolean column per trigger, plus `any` of them."""
    out = pd.DataFrame({t: TRIGGERS[t][1](panel).fillna(False)
                        .astype(bool) for t in triggers},
                       index=panel.index)
    out["any"] = out.any(axis=1)
    return out


def watch_record(panel: pd.DataFrame, flags: pd.DataFrame
                 ) -> pd.DataFrame:
    """Each flag's history, on months whose next 12 months are known:
    company-months flagged, companies flagged, the hit rate (share of
    flagged months followed by a default within 12 months), defaults
    caught (flagged at least once in the 12 months before), companies
    flagged that did not default within 12 months of any flag (false
    alarms), and the median months of warning for those caught."""
    known = panel["default_12m"].notna()
    y = panel["default_12m"] == 1
    defaulters = panel.loc[known & y, "company_id"].nunique()
    rows = []
    for name in flags.columns:
        f = flags[name] & known
        hit = f & y
        caught = panel.loc[hit, "company_id"].unique()
        alarms = set(panel.loc[f, "company_id"]) - set(
            panel.loc[hit, "company_id"])
        first = panel[hit].groupby("company_id")["month"].min()
        dmon = panel[hit].groupby("company_id")["default_month"].first()
        lead = ((dmon - first).dt.days / 30.44).round()
        rows.append({"flag": name, "months": int(f.sum()),
                     "companies": int(panel.loc[f, "company_id"]
                                      .nunique()),
                     "hit_rate": float(y[f].mean()) if f.any() else 0.0,
                     "caught": len(caught), "defaults": defaulters,
                     "false_alarms": len(alarms),
                     "warning": float(lead.median()) if len(lead)
                     else np.nan})
    return pd.DataFrame(rows)


# ----------------------------------------------------- the pack

WIDTH = 68


def table(header, rows, widths, aligns=None) -> list[str]:
    """Rows as fixed-width text: the first column left-aligned, the
    rest right-aligned unless `aligns` says otherwise."""
    aligns = aligns or ["<"] + [">"] * (len(widths) - 1)
    fmt = "".join(f"{{:{a}{w}}}" for a, w in zip(aligns, widths))
    out = [fmt.format(*header).rstrip()] if header else []
    out += [fmt.format(*r).rstrip() for r in rows]
    if max(len(s) for s in out) > WIDTH:
        raise ValueError("a pack table is wider than the page")
    return out


def section(title: str) -> list[str]:
    return ["", title.upper(), "-" * len(title)]


def _month_mask(day: pd.Series, first: str, last: str) -> pd.Series:
    d = day.astype(str)
    return (d >= first) & (d <= last)


def _stability(con, raw, card, as_of, alerts) -> list[str]:
    """Section 1: who is applying, against two references."""
    from ballast.decision import engine
    m0 = as_of.replace(day=1).isoformat()
    y0 = (pd.Timestamp(m0) - pd.DateOffset(months=12)).date().isoformat()
    day = raw["app_date"].astype(str)
    now = day >= m0
    year = (day >= y0) & (day < m0)
    rows = []
    for prod in ("personal", "card", "auto"):
        s = raw["product"].astype(str).eq(prod)
        x = raw["mark1_score"].astype(float)
        fixed = s & (day < "2017-01-01")
        a, r12, rf = x[s & now], x[s & year], x[fixed]
        p12, pf = psi(r12, a), psi(rf, a)
        noise = psi_noise(len(a), len(r12))
        rows.append((f"{prod}, Mark I", f"{len(a):,}", f"{a.mean():.1f}",
                     f"{a.mean() - rf.mean():+.1f}", f"{pf:.3f}",
                     f"{p12:.3f}", f"{noise:.3f}"))
        if p12 >= noise or pf >= psi_noise(len(a), len(rf)):
            alerts.append(f"{prod} Mark I {a.mean() - rf.mean():+.1f} "
                          f"points on 2016 (PSI {pf:.3f})")
    pl = raw[raw["product"].astype(str).eq("personal")]
    pday = pl["app_date"].astype(str)
    chars = engine.prepare(pl)
    sc = card.score(chars).astype(float)
    ref = _month_mask(pday, "2023-01-01", "2024-06-30")
    pn = pday >= m0
    p_ref = psi(sc[ref], sc[pn])
    noise = psi_noise(int(pn.sum()), int(ref.sum()))
    rows.append(("personal, Mark II-R", f"{int(pn.sum()):,}",
                 f"{sc[pn].mean():.1f}",
                 f"{sc[pn].mean() - sc[ref].mean():+.1f}", f"{p_ref:.3f}",
                 f"{psi(sc[(pday >= y0) & (pday < m0)], sc[pn]):.3f}",
                 f"{noise:.3f}"))
    lines = card.line_points(chars)
    ca = characteristic_analysis(lines[ref.to_numpy()],
                                 lines[pn.to_numpy()])
    top = ca.iloc[0]
    out = section("1 Who is applying: score stability")
    out += [f"December {as_of.year} against the 12 months before and a "
            "fixed reference",
            "(Mark I: 2016's applicants; Mark II-R: Jan 2023-Jun 2024)"]
    out += table(("score", "apps", "mean", "shift", "PSI fix", "PSI 12m",
                  "noise"), rows, (21, 6, 7, 7, 9, 9, 8))
    hit = raw["bureau_score"].astype(float) > 0
    b = raw["bureau_score"].astype(float)
    bp = psi(b[hit & year], b[hit & now])
    out.append(f"bureau score (all applicants with a file): PSI 12m "
               f"{bp:.3f}")
    out.append(f"Mark II-R's line that moved most: {top.line}")
    out.append(f"  PSI {top.psi:.3f}, {top['shift']:+.1f} points")
    if top.psi >= PSI_AMBER:
        alerts.append(f"Mark II-R line {top.line} moved "
                      f"(PSI {top.psi:.3f})")
    return out


def _early(con, as_of, alerts) -> list[str]:
    """Section 2: early arrears by vintage, against the eight quarters
    before those shown."""
    out = section("2 Early arrears by quarter opened")
    out.append("share of loans 30+ days behind by month 3 / 60+ by "
               "month 6;")
    out.append("norm = the mean of the eight quarters before those "
               "shown")
    rows = []
    for prod in ("personal", "card"):
        q = early_reads(con, prod, as_of=as_of)
        shown = q[q["e3"].notna()].tail(5)
        before = q.loc[:shown.index[0] - 1].tail(8)
        n3, n6 = before["e3"].mean(), before["e6_60"].mean()
        for r in shown.itertuples():
            flag = ""
            for v, norm in ((r.e3, n3), (r.e6_60, n6)):
                if np.isfinite(v):
                    se = np.sqrt(norm * (1 - norm) / r.loans)
                    if (v - norm) / se >= Z_ALARM:
                        flag = "high"
            if flag:
                alerts.append(f"{prod} {r.vintage} early arrears high")
            e6 = f"{r.e6_60:.2%}" if np.isfinite(r.e6_60) else ".."
            rows.append((prod if r.Index == shown.index[0] else "",
                         r.vintage, f"{r.loans:,}", f"{r.e3:.2%}", e6,
                         flag))
        rows.append(("", "norm", "", f"{n3:.2%}", f"{n6:.2%}", ""))
    out += table(("product", "opened", "loans", "30+ m3", "60+ m6", ""),
                 rows, (10, 9, 7, 9, 9, 6))
    return out


def _band(con, raw, card, cutoff, as_of, alerts) -> list[str]:
    """Section 3: the band just above the cut-off."""
    from ballast.decision import engine
    b = raw[raw["product"].astype(str).eq("personal")
            & raw["outcome"].astype(str).eq("booked")]
    s = pd.DataFrame({"account_id": b["account_id"].astype(str),
                      "day": b["app_date"].astype(str),
                      "score": card.score(engine.prepare(b))})
    s = s.merge(early_accounts(con, "personal"), left_on="account_id",
                right_on="root_id")
    near = s["score"].between(cutoff, cutoff + 15)
    old = s[near & _month_mask(s["day"], "2023-01-01", "2024-06-30")]
    new = s[near & (s["day"] >= f"{as_of.year}-01-01")
            & (s["seen"] >= 3)]
    z = mean_shift_z(old["e3"], new["e3"])
    out = section(f"3 The band above the cut-off ({cutoff}-"
                  f"{cutoff + 15})")
    out.append(f"{as_of.year} loans with 3+ months: {len(new):,}, 30+ by "
               f"month 3 {new['e3'].mean():.2%}")
    out.append(f"same band, Jan 2023-Jun 2024: {len(old):,} loans, "
               f"{old['e3'].mean():.2%}; z {z:+.1f}")
    if z >= Z_ALARM:
        alerts.append("early arrears high just above the cut-off")
    return out


def _calibration(card, alerts) -> list[str]:
    """Section 4: is Mark II-R keeping its promises and its ranking?"""
    from ballast.scorecard import sample
    s = sample.load_sample()
    s = s[s["outcome"].isin(["good", "bad"])]
    score = card.score(s)
    bad = s["outcome"].eq("bad").astype(int)
    q = pd.to_datetime(s["app_date"].astype("datetime64[s]")).dt.to_period(
        "Q").astype(str)
    c = calibration_drift(pts.bad_rate_at(score), bad, q).tail(4)
    out = section("4 Mark II-R: promises and ranking (complete windows)")
    out += table(("quarter", "loans", "promised", "seen", "interval", ""),
                 [(r.period, f"{r.n:,}", f"{r.promised:.2%}",
                   f"{r.seen:.2%}", f"{r.lo:.2%}-{r.hi:.2%}",
                   "out" if r.outside else "")
                  for r in c.itertuples()], (10, 7, 10, 8, 15, 5))
    day = s["app_date"].astype(str)
    dev, oot = day < "2023-01-01", day >= "2023-01-01"
    g_dev = metrics.gini(score[dev], bad[dev])
    g_oot = metrics.gini(score[oot], bad[oot])
    out.append(f"Gini: development 2016-22 {g_dev:.3f}; since 2023 "
               f"{g_oot:.3f}")
    if c["outside"].any():
        alerts.append("Mark II-R promise outside the seen interval in "
                      + ", ".join(c.loc[c["outside"], "period"]))
    return out


def _behaviour(con, as_of, alerts) -> list[str]:
    """Section 5: the existing book by behavioural score band."""
    scores = load_behaviour()
    prev = (pd.Timestamp(as_of) - pd.DateOffset(months=3)) \
        + pd.offsets.MonthEnd(0)
    f = behaviour_frame(con, [prev.date(), as_of], as_of=as_of)
    f["score"] = 0
    f["promised"] = 0.0
    for prod, b in scores.items():
        m = f["product"].eq(prod)
        f.loc[m, "score"] = b.score(f[m])
        f.loc[m, "promised"] = b.bad_rate(f[m])
    edges, names = [0, 560, 590, 610, 999], ["<560", "560-589",
                                             "590-609", "610+"]
    f["band"] = pd.cut(f["score"], edges, right=False, labels=names)
    out = section(f"5 Existing customers: behavioural score, "
                  f"{as_of:%b %Y}")
    rows = []
    for prod in ("personal", "card"):
        mon_ = f["month"].astype(str).str[:10]
        now = f[f["product"].eq(prod) & (mon_ == as_of.isoformat())]
        was = f[f["product"].eq(prod)
                & (mon_ == prev.date().isoformat())]
        bal = now["balance_cents"].sum()
        for k, name in enumerate(names):
            g, h = now[now["band"] == name], was[was["band"] == name]
            rows.append((prod if k == 0 else "", name, f"{len(g):,}",
                         f"{g['balance_cents'].sum() / bal:.1%}",
                         f"{len(g) / len(now) - len(h) / len(was):+.1%}",
                         f"{g['promised'].mean():.2%}"))
        exp = now["promised"].mean()
        rows.append(("", "all", f"{len(now):,}", "100%", "",
                     f"{exp:.2%}"))
        exp_was = was["promised"].mean()
        if exp - exp_was > 0.1 * exp_was:
            alerts.append(f"{prod} behavioural bad rate up "
                          f"{exp_was:.2%} -> {exp:.2%}")
    out += table(("product", "band", "accounts", "balance",
                  "vs Sep", "12m bad"), rows, (10, 9, 10, 10, 9, 10))
    out.append("accounts open, not in default, at most two payments "
               "behind")
    return out


def _business(con, as_of, alerts) -> list[str]:
    """Section 6: the commercial watchlist at the month end."""
    p = business_panel(con, end=as_of, as_of=as_of)
    w = watch(p)
    early = w[list(WATCHLIST)].any(axis=1)
    last = p["month"] == pd.Timestamp(as_of)
    before = p["month"] == (pd.Timestamp(as_of) - pd.offsets.MonthEnd(1))
    on = p[last & (early | w["grade_8"])]
    prev = set(p.loc[before & (early | w["grade_8"]), "company_id"])
    names = dict(con.execute("SELECT company_id, name FROM companies")
                 .fetchall())
    out = section(f"6 Commercial clients: the watchlist, {as_of:%b %Y}")
    out.append(f"{int(last.sum())} clients; {len(on)} on the list "
               f"({int((last & w['grade_8']).sum())} by grade 8+, "
               f"{int((last & early).sum())} by early warning)")
    rows = []
    for i in on[early[on.index]].index:
        r = p.loc[i]
        why = [t for t in WATCHLIST if w.loc[i, t]]
        new = "new" if r.company_id not in prev else ""
        rows.append((r.company_id, names[r.company_id],
                     f"{int(r.grade)}", f"{r.revolver_use:.0%}",
                     ", ".join(why), new))
    if rows:
        out += table(("client", "name", "grade", "drawn", "trigger",
                      ""), rows, (7, 26, 6, 7, 13, 4),
                     ["<", "<", ">", ">", ">", ">"])
    fresh = [r for r in rows if r[-1]]
    if fresh:
        alerts.append(f"{len(fresh)} new on the commercial watchlist")
    return out


def _sme(con, as_of) -> list[str]:
    """Section 7: SME-1 with bank data, run beside SME-1 as a shadow."""
    from ballast.commercial import sme
    from ballast.scorecard import model as md
    from ballast.scorecard import woe
    s = sme.sample(con)
    o = s[s["ob"]].reset_index(drop=True)
    o["sme1"] = o["sme1_score"] / 20
    bins, _ = woe.fit_binset(o, o["bad"], {k: sme.SPEC[k]
                                           for k in sme.BANK_FIELDS})
    X = woe.encode(o, bins)
    X["sme1"] = o["sme1"]
    r = md.fit(X, 1 - o["bad"], sme.BANK_FIELDS + ["sme1"])
    apps = con.execute("SELECT * FROM sme_applications "
                       "WHERE year(app_date) = ? AND product IN "
                       "('sme_term', 'sme_overdraft') ORDER BY app_id",
                       [as_of.year]).df()
    apps = apps[apps["ob_avg_balance_cents"].notna()].reset_index(
        drop=True)
    c = sme.characteristics(apps, sme.owner_map(con.execute(
        "SELECT * FROM sme_applications").df()))
    Y = woe.encode(c, bins)
    Y["sme1"] = apps["sme1_score"] / 20
    shadow = pd.Series(md.log_odds(r, Y), index=apps.index)
    ok = apps["decision"].eq("approve")
    k = shadow.quantile(1 - ok.mean())
    both = (shadow >= k) == ok
    out = section(f"7 Small business: SME-1 + bank data (shadow), "
                  f"{as_of.year}")
    out.append(f"{len(apps):,} applications with bank data; SME-1 "
               f"approved {ok.mean():.1%}")
    out.append(f"shadow at the same approval rate agrees on "
               f"{both.mean():.1%};")
    out.append(f"  it would approve {int(((shadow >= k) & ~ok).sum())} "
               f"SME-1 declined and decline "
               f"{int(((shadow < k) & ok).sum())} it approved")
    return out


def _fairness(con, raw, p, card, alerts) -> list[str]:
    """Section 8: the fair-lending indicators Chapter 13 asked for."""
    from ballast import fairness
    from ballast.decision import engine
    from ballast.scorecard import reject, sample
    g = fairness.monitoring(con).set_index("app_id")["gender"]
    pl = raw[raw["product"].astype(str).eq("personal")]
    year = pl["app_date"].astype(str).str[:4]
    out = section("8 Fair lending")
    out.append("approval, women over men (F/M), 95% interval")
    rng = np.random.default_rng(SEED)
    rows = []
    last = int(year.max())
    for y in range(last - 2, last + 1):
        a = pl[year == str(y)]
        gg = g.reindex(a["app_id"].astype(str)).to_numpy()
        ok = a["decision"].astype(str).eq("approve").to_numpy()
        air = fairness.adverse_impact_ratio(ok, gg, "F", "M")
        lo, hi = fairness.air_interval(ok, gg, "F", "M", rng)
        rows.append((f"Fernhill {y}", f"{air:.3f}", f"{lo:.3f}-{hi:.3f}"))
    a = pl[year == str(last)]
    d = engine.decide_all(a, p, card)
    gg = g.reindex(a["app_id"].astype(str)).to_numpy()
    ok = (d["decision"] == "approve").to_numpy()
    air = fairness.adverse_impact_ratio(ok, gg, "F", "M")
    lo, hi = fairness.air_interval(ok, gg, "F", "M", rng)
    rows.append((f"Ballast {last}", f"{air:.3f}", f"{lo:.3f}-{hi:.3f}"))
    if hi < 1:
        alerts.append(f"Ballast's {last} approval ratio F/M {air:.3f}, "
                      "interval below 1")
    out += table(("decisions", "ratio", "interval"), rows, (16, 8, 14))
    s = sample.load_sample()
    s = s[s["outcome"].isin(["good", "bad"])]
    seen = s["outcome"].eq("bad").astype(int)
    prom = pts.bad_rate_at(card.score(s))
    band = fairness.age_band(s["age"]).set_axis(s.index)
    t = pd.DataFrame({"b": band, "y": seen, "p": prom}).groupby(
        "b", observed=True)[["y", "p"]].mean()
    out.append("seen / promised bad rate by age: " + "  ".join(
        f"{k} {v.y / v.p:.2f}" for k, v in t.iterrows()
        if k in ("18-24", "35-49", "65+")))
    m = (d["stage"] == "score") & (d["decision"] != "approve")
    ref = fairness.cutoff_reference(
        card, reject.frames(reject.applicants(con))["oot"], p.cutoff)
    first = fairness.cutoff_reasons(card, engine.prepare(a[m]),
                                    ref).str[0].value_counts()
    out.append(f"first reasons, {int(m.sum()):,} score declines and "
               f"referrals: {len(first)} different;")
    out.append(f"  most common {first.index[0]} "
               f"{first.iloc[0] / first.sum():.0%}, then "
               f"{first.index[1]} {first.iloc[1] / first.sum():.0%}")
    if first.iloc[0] / first.sum() > 0.5:
        alerts.append("one first reason given to over half the declines")
    return out


def _fraud(con, raw, as_of, alerts) -> list[str]:
    """Section 9: fraud referrals and loans that never paid."""
    from ballast import fraud
    pl = raw[raw["product"].astype(str).eq("personal")]
    y = pl["app_date"].astype(str).str[:4]
    out = section("9 Fraud")
    a = pl[y == str(as_of.year)]
    ref = fraud.referred(fraud.flags(a))
    ch = a["channel"].astype(str)
    out.append(f"{as_of.year} referrals by Ballast's rules: "
               f"{int(ref.sum())} ({ref.sum() / 12:.1f} a month)")
    out.append("  " + ", ".join(f"{c} {int(ref[ch == c].sum())}"
                                for c in sorted(ch.unique())))
    fp = fraud.first_payments(con, "personal").dropna(
        subset=["never_paid"])
    opened = fp["open_date"].astype(str).str[:4]
    rows = []
    for c in sorted(fp["channel"].astype(str).unique()):
        cells = []
        for yy in (as_of.year - 1, as_of.year):
            g = fp[(opened == str(yy)) & fp["channel"].astype(str).eq(c)]
            cells += [f"{len(g):,}", f"{g['never_paid'].mean():.2%}"]
        rows.append((c, *cells))
        last = fp[(opened == str(as_of.year))
                  & fp["channel"].astype(str).eq(c)]["never_paid"]
        before = fp[(opened == str(as_of.year - 1))
                    & fp["channel"].astype(str).eq(c)]["never_paid"]
        if len(last) and last.mean() > 2 * max(before.mean(), 0.002):
            alerts.append(f"never-paid loans up in {c}")
    out.append("loans that never paid (first three payments missed)")
    out += table(("channel", f"{as_of.year - 1}", "never", f"{as_of.year}",
                  "never"), rows, (10, 8, 8, 8, 8))
    return out


def pack(con, as_of: dt.date = AS_OF) -> str:
    """The monthly monitoring pack, as text no wider than WIDTH."""
    from ballast import data
    from ballast.decision import engine
    from ballast.decision import policy as pol
    p = pol.load_policy()
    card = engine.load_champion(p)
    raw = data.load_applications(con, unknowns=False)
    raw = raw[raw["app_date"].astype(str) <= as_of.isoformat()]
    alerts: list[str] = []
    body = (_stability(con, raw, card, as_of, alerts)
            + _early(con, as_of, alerts)
            + _band(con, raw, card, p.cutoff, as_of, alerts)
            + _calibration(card, alerts)
            + _behaviour(con, as_of, alerts)
            + _business(con, as_of, alerts)
            + _sme(con, as_of)
            + _fairness(con, raw, p, card, alerts)
            + _fraud(con, raw, as_of, alerts))
    head = ["FERNHILL BANK  CREDIT MONITORING PACK",
            f"Month end {as_of:%d %B %Y}; produced by Ballast",
            "", "FOR ATTENTION"]
    head += [f"  {i + 1}. {a}" for i, a in enumerate(alerts)] or [
        "  nothing beyond its limits"]
    lines = head + body
    too_wide = [s for s in lines if len(s) > WIDTH]
    if too_wide:
        raise ValueError("pack lines wider than "
                         f"{WIDTH}: {too_wide}")
    return "\n".join(lines) + "\n"


def save_pack(text: str, as_of: dt.date = AS_OF,
              path: Path = MONITORING) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    out = path / f"pack_{as_of:%Y-%m}.txt"
    out.write_text(text)
    return out
