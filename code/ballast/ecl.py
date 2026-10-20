"""Expected credit loss: IFRS 9 staging and measurement, and CECL.

A provision is the loss a lender expects on the loans it holds,
booked before the loss happens. This module computes it, account by
account, for Fernhill's retail and small-business accounts and its
commercial facilities, at any month end:

- **staging** (IFRS 9): stage 3 is an account in default; stage 2 an
  account whose credit risk has increased significantly since it was
  made (Fernhill's rule is `SICR_RATIO` and `SICR_POINTS` on the
  12-month PD, a 30-day backstop, a year's watch after a cure, and
  the commercial watchlist); stage 1 is everything else;
- **measurement**: month by month, the chance of defaulting that
  month (a hazard from Chapter 18, lifted in the first year for an
  account's arrears and use of its limit), times the loss given
  default (Chapter 19, discounted at the contract rate), times the
  exposure that month, discounted at the effective interest rate;
  twelve months for stage 1, the whole life for stages 2 and 3;
- **scenarios**: the same sum under each of the scenarios published
  for the date, weighted by their probabilities;
- **CECL**: lifetime losses for every account, with the forecast
  reverting to the long run after two years and no provision for
  limits Fernhill could cancel.

    import fernhill
    from ballast import ecl
    con = fernhill.connect()
    r = ecl.run(con, ecl.AS_OF)            # one row per account
    ecl.summary(r)                          # by product and stage

The parameters come from `ballast.parameters`; the arrears and
utilisation uplifts and the prepayment rates are measured here, on
history that had happened by the date of the run.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from ballast import performance as perf
from ballast.config import AS_OF, BALLAST
from ballast.parameters import ead as eadm
from ballast.parameters import lgd as lgdm
from ballast.parameters import pd as pdm

# ------------------------------------------------- Fernhill's choices
SICR_RATIO = 2.0        # 12-month PD at least twice origination's
SICR_POINTS = 0.01      # ... and at least one point higher
BACKSTOP_MISSED = 1     # one payment missed (30 days past due)
CURE_WATCH = 12         # months in stage 2 after a cure from default
WATCHLIST = (9, 10)     # commercial grades on the watchlist
LIFE = {"card": 60, "sme_overdraft": 36}    # behavioural, months
FORECAST_YEARS = 5      # scenarios run to December 2030, then held
CECL_RS_MONTHS = 24     # CECL: reasonable and supportable forecast
CECL_REVERT = 12        # ... then straight back to the long run
NEW_CLIENT_GRADE = 6    # a commercial client not yet reviewed
WEIGHTED = ("upside", "base", "downside", "severe")
INSTALMENT = ("personal", "auto", "mortgage", "sme_term",
              "sme_emergency")
REVOLVING = ("card", "sme_overdraft")
RETAIL = INSTALMENT + REVOLVING
FREE_MONTHS = {"sme_emergency": 12}         # payment-free start
OUT = BALLAST / "ecl"


# ---------------------------------------------------------- scenarios

def scenarios(con, as_of=AS_OF) -> pd.DataFrame:
    """Each weighted scenario's weight and monthly unemployment path
    for the 60 months after `as_of`.

    Fernhill's archive holds only the set published for 31 December
    2025. For an earlier date the set is rebuilt by moving that one
    up or down to start from the unemployment of the earlier date.
    """
    s = con.execute("""SELECT scenario, weight, month, unemployment_pct
                       FROM scenarios WHERE as_of = ? AND weight > 0
                       ORDER BY scenario, month""", [AS_OF]).df()
    shift = 0.0
    if pd.Timestamp(as_of) != pd.Timestamp(AS_OF):
        u = dict(con.execute("SELECT month, unemployment_pct "
                             "FROM macro").fetchall())
        shift = u[pd.Timestamp(as_of).date()] - u[AS_OF]
    rows = [{"scenario": k, "weight": float(g.weight.iloc[0]),
             "path": g.unemployment_pct.to_numpy() + shift,
             "lgd": "downturn" if k == "severe" else "lgd"}
            for k, g in s.groupby("scenario")]
    out = pd.DataFrame(rows).set_index("scenario").loc[list(WEIGHTED)]
    out.attrs["shift"] = float(shift)
    return out


def path(u: np.ndarray, months: int, long_run: float | None = None
         ) -> np.ndarray:
    """A scenario path stretched to `months`: held at its last value
    after December 2030, or (CECL, with `long_run`) back to the long
    run in a straight line after the forecast period."""
    out = np.r_[u, np.repeat(u[-1], max(months - len(u), 0))][:months]
    if long_run is not None:
        k = np.arange(months)
        w = np.clip((k - CECL_RS_MONTHS + 1) / CECL_REVERT, 0, 1)
        out = (1 - w) * out + w * long_run
    return out


# --------------------------------------------- parameters at a date

def prepayment(con, as_of=AS_OF) -> dict:
    """Monthly prepayment rate of each instalment product over the
    three years to `as_of`: loans prepaid in a month over loans open
    and not yet at their last scheduled month."""
    lo = pd.Timestamp(as_of) - pd.DateOffset(years=3)
    r = con.execute("""
        WITH m AS (
            SELECT p.product, p.status,
                   date_diff('month', a.open_date, p.month) AS mob,
                   a.term_months
            FROM performance p JOIN accounts a USING (account_id)
            WHERE p.month > ? AND p.month <= ?)
        SELECT product, count(*) FILTER (WHERE status = 'prepaid')
               / count(*) AS rate
        FROM m WHERE mob >= 1 AND mob < term_months
          AND status IN ('up_to_date', 'arrears', 'default',
                         'prepaid', 'repaid')
        GROUP BY 1 ORDER BY 1""", [lo.date(), as_of]).fetchall()
    return {p: float(x) for p, x in r if p in INSTALMENT}


def pools(missed, worst12, util, product) -> np.ndarray:
    """Each account's pool: '30' or '60' if payments are missed now,
    'recent' if up to date after a miss in the last year, and for a
    clean revolving account its use of the limit."""
    m = np.asarray(missed)
    w = np.nan_to_num(np.asarray(worst12, dtype=float))
    u = np.asarray(util, dtype=float)
    rev = np.isin(np.asarray(product), REVOLVING)
    clean = np.where(~rev, "clean",
                     np.where(u >= 0.9, "u90+",
                              np.where(u >= 0.5, "u50-90", "u<50")))
    return np.where(m >= 2, "60", np.where(m == 1, "30",
                    np.where(w >= 1, "recent", clean)))


def uplifts(con, as_of=AS_OF) -> pd.DataFrame:
    """How much more (or less) often each pool defaults in the next
    twelve months than the product's accounts as a whole.

    Measured on quarter ends whose twelve months had passed by
    `as_of`, for accounts open, not in default and at most two
    payments behind (the population Chapter 18's hazards describe).
    A pool with fewer than 20 defaults borrows the all-product ratio.
    """
    perf.prepare(con)
    eps = perf.default_episodes(con, pdm.DEFINITION)
    con.register("ecl_eps", eps[["account_id", "default_month",
                                 "cure_month"]])
    last = (pd.Timestamp(as_of) - pd.DateOffset(months=12)).date()
    df = con.execute("""
        WITH h AS (
            SELECT root_id, product, month, missed, status,
                   balance_cents / nullif(limit_cents, 0) AS util,
                   max(missed) OVER (PARTITION BY root_id ORDER BY month
                       ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS w12
            FROM history),
        q AS (SELECT * FROM h
              WHERE month(month) % 3 = 0 AND month <= ?
                AND status IN ('up_to_date', 'arrears') AND missed <= 2
                AND NOT EXISTS (
                    SELECT 1 FROM ecl_eps e
                    WHERE e.account_id = h.root_id
                      AND e.default_month <= h.month
                      AND (e.cure_month IS NULL
                           OR e.cure_month > h.month)))
        SELECT product, missed, w12, util,
               EXISTS (SELECT 1 FROM ecl_eps e
                       WHERE e.account_id = q.root_id
                         AND e.default_month > q.month
                         AND e.default_month
                             <= q.month + INTERVAL 12 MONTH) AS y
        FROM q""", [last]).df()
    con.unregister("ecl_eps")
    df["pool"] = pools(df.missed, df.w12, df.util, df["product"])
    rate = df.groupby("product")["y"].mean()
    g = df.groupby(["product", "pool"])["y"].agg(["size", "sum"])
    g["rate"] = g["sum"] / g["size"]
    allp = df.groupby("pool")["y"].mean() / df["y"].mean()
    g["uplift"] = g["rate"] / g.index.get_level_values(0).map(rate)
    thin = g["sum"] < 20
    g.loc[thin, "uplift"] = g.index[thin].get_level_values(1).map(allp)
    return g.rename(columns={"size": "n", "sum": "defaults"})


def lgds(con) -> pd.DataFrame:
    """Loss given default for IFRS 9: Chapter 19's workouts discounted
    at each loan's own rate, long run and downturn, by product; and
    the commercial book's, secured and unsecured, from its workouts.
    """
    w = lgdm.workouts(con)
    f = lgdm.cash_flows(con, w)
    r = lgdm.discount_rates(con, w, "contract")
    rows = {}
    for p, g in w.groupby("product"):
        e = lgdm.estimate(g, f, r)
        rows[p] = (e["lgd"], e["downturn"], e["workouts"])
    c = commercial_lgd(con)
    for k, g in c.groupby("secured"):
        loss = (g.lgd * g.ead_cents).sum() / g.ead_cents.sum()
        key = "commercial_secured" if k else "commercial_unsecured"
        rows[key] = (float(loss), float(loss), int(len(g)))
    return pd.DataFrame.from_dict(
        rows, orient="index", columns=["lgd", "downturn", "workouts"])


def commercial_lgd(con) -> pd.DataFrame:
    """Each defaulted commercial facility: drawn at default, what came
    back (restructuring or liquidation, less costs), discounted to the
    month of default at the facility's rate then (reference rate plus
    margin), and its LGD floored at zero."""
    d = con.execute("""
        WITH d AS (SELECT facility_id, month AS dm, drawn_cents
                   FROM facility_months WHERE status = 'defaulted')
        SELECT d.facility_id, f.secured, d.dm,
               d.drawn_cents AS ead_cents,
               (m.policy_rate_pct + f.margin_bps / 100) AS rate_pct,
               r.month AS rm, coalesce(r.amount_cents, 0) AS amount
        FROM d JOIN facilities f USING (facility_id)
        JOIN market_rates m ON m.month = d.dm
        LEFT JOIN corporate_recoveries r USING (facility_id)
        ORDER BY 1, rm""").df()
    t = ((pd.to_datetime(d.rm).dt.year - pd.to_datetime(d.dm).dt.year)
         * 12 + pd.to_datetime(d.rm).dt.month
         - pd.to_datetime(d.dm).dt.month).fillna(0)
    d["pv"] = d.amount / (1 + d.rate_pct / 1200) ** t
    g = d.groupby("facility_id").agg(
        secured=("secured", "first"), ead_cents=("ead_cents", "first"),
        pv=("pv", "sum"))
    g["lgd"] = (1 - g.pv / g.ead_cents).clip(lower=0)
    return g.reset_index()


def card_payment_rate(con, as_of=AS_OF) -> float:
    """Share of the balance up-to-date cardholders paid each month
    over the year to `as_of` (CECL runs card balances off at it)."""
    lo = pd.Timestamp(as_of) - pd.DateOffset(years=1)
    return float(con.execute("""
        SELECT sum(least(paid_cents, balance_cents))
               / sum(balance_cents)
        FROM performance WHERE product = 'card' AND month > ?
          AND month <= ? AND status = 'up_to_date'
          AND balance_cents > 0""", [lo.date(), as_of]).fetchone()[0])


def parameters(con, as_of=AS_OF) -> dict:
    """Everything a run needs that is estimated, once per date."""
    u = pdm.unemployment(con)
    lo, hi = (pd.Timestamp(x) for x in pdm.LONG_RUN)
    return {"hazards": pdm.load_hazards(),
            "commercial": pdm.load_json("pd_commercial.json"),
            "ccf": eadm.load(),
            "lgd": lgds(con),
            "prepay": prepayment(con, as_of),
            "uplift": uplifts(con, as_of),
            "card_paydown": card_payment_rate(con, as_of),
            "long_run_u": float(u[(u.index >= lo)
                                  & (u.index <= hi)].mean()),
            "scenarios": scenarios(con, as_of)}


# --------------------------------------------------------- the books

def retail_book(con, as_of=AS_OF) -> pd.DataFrame:
    """Every retail and small-business account open on `as_of`, with
    what the engine needs: balance, limit, rate, months on book and
    to maturity, score band, arrears now and over the past year, use
    of the limit, and whether it is in default or lately cured."""
    perf.prepare(con)
    lo = (pd.Timestamp(as_of) - pd.DateOffset(months=12)).date()
    b = con.execute("""
        WITH cur AS (
            SELECT * FROM history WHERE month = ?
              AND status IN ('up_to_date', 'arrears', 'default')),
        past AS (
            SELECT root_id, max(missed) AS worst12
            FROM history WHERE month >= ? AND month < ? GROUP BY 1),
        hol AS (
            SELECT root_id,
                   count(*) FILTER (WHERE payment_holiday) AS hol
            FROM history WHERE month <= ? GROUP BY 1)
        SELECT c.account_id, c.root_id, c.product, c.balance_cents,
               coalesce(c.limit_cents, 0) AS limit_cents, c.missed,
               c.status, c.rate_pct, c.payment_holiday,
               date_diff('month', c.root_open, c.month) AS mob,
               date_diff('month', a.open_date, c.month) AS age,
               a.term_months, hol.hol, past.worst12, ap.mark1_score
        FROM cur c
        JOIN accounts a ON a.account_id = c.account_id
        JOIN accounts r ON r.account_id = c.root_id
        LEFT JOIN applications ap ON ap.app_id = r.app_id
        LEFT JOIN past USING (root_id) LEFT JOIN hol USING (root_id)
        ORDER BY c.account_id""", [as_of, lo, as_of, as_of]).df()
    loans = pdm.personal_loans(con)[["account_id", "score"]]
    b = b.merge(loans, how="left", left_on="root_id",
                right_on="account_id", suffixes=("", "_l"))
    b["score"] = b["score"].where(b["product"] == "personal",
                                  b["mark1_score"])
    b["band"] = "all"
    for p, edges in pdm.SCORE_EDGES.items():
        sel = b["product"] == p
        b.loc[sel, "band"] = pdm.band(b.loc[sel, "score"], edges)
    b["util"] = np.where(b.limit_cents > 0,
                         b.balance_cents / b.limit_cents.where(
                             b.limit_cents > 0, 1), np.nan)
    b["remaining"] = np.where(
        b["product"].isin(INSTALMENT),
        np.maximum(b.term_months + b.hol.fillna(0) - b.age, 1),
        b["product"].map(LIFE).fillna(0)).astype(int)
    eps = perf.default_episodes(con, pdm.DEFINITION)
    dm = pd.to_datetime(eps.default_month)
    cm = pd.to_datetime(eps.cure_month)
    t = pd.Timestamp(as_of)
    in_d = eps.account_id[(dm <= t) & (cm.isna() | (cm > t))]
    watch = t - pd.DateOffset(months=CURE_WATCH)
    cured = eps.account_id[(cm <= t) & (cm > watch)]
    b["in_default"] = b.root_id.isin(in_d)
    b["cured"] = b.root_id.isin(cured) & ~b["in_default"]
    b["pool"] = pools(b.missed, b.worst12, b.util, b["product"])
    cols = ["account_id", "root_id", "product", "balance_cents",
            "limit_cents", "rate_pct", "mob", "age", "remaining",
            "band",
            "missed", "worst12", "util", "payment_holiday", "pool",
            "in_default", "cured"]
    return b[cols].reset_index(drop=True)


def commercial_book(con, as_of=AS_OF) -> pd.DataFrame:
    """Every commercial facility on `as_of`, with its grade now and
    when it was made, drawn amount, limit, months to maturity and
    rate (the reference rate then plus the margin)."""
    f = con.execute("""
        WITH fm AS (
            SELECT facility_id,
                   coalesce(max(drawn_cents) FILTER (
                       WHERE status = 'defaulted'), max(drawn_cents))
                       AS drawn_cents,
                   max(limit_cents) AS limit_cents,
                   bool_or(status = 'defaulted') AS defaulted
            FROM facility_months WHERE month = ? GROUP BY 1),
        g AS (SELECT company_id, rating_date, internal_grade AS grade
              FROM ratings WHERE internal_grade IS NOT NULL)
        SELECT f.facility_id AS account_id, f.company_id, f.kind,
               f.secured, fm.drawn_cents AS balance_cents,
               fm.limit_cents, fm.defaulted,
               date_diff('month', ?::DATE, f.maturity_date)
                   AS remaining,
               (SELECT policy_rate_pct FROM market_rates
                WHERE month = ?) + f.margin_bps / 100 AS rate_pct,
               (SELECT grade FROM g WHERE g.company_id = f.company_id
                  AND g.rating_date <= ?
                ORDER BY rating_date DESC LIMIT 1) AS grade,
               coalesce(
                 (SELECT grade FROM g WHERE g.company_id = f.company_id
                    AND g.rating_date <= f.start_date
                  ORDER BY rating_date DESC LIMIT 1),
                 (SELECT grade FROM g WHERE g.company_id = f.company_id
                  ORDER BY rating_date LIMIT 1)) AS grade0
        FROM facilities f JOIN fm USING (facility_id)
        ORDER BY 1""", [as_of, as_of, as_of, as_of]).df()
    f["product"] = "commercial_" + f["kind"]
    f["unrated"] = f["grade"].isna()
    f["grade"] = f["grade"].fillna(NEW_CLIENT_GRADE).astype(int)
    f["grade0"] = f["grade0"].fillna(f["grade"]).astype(int)
    f["remaining"] = f["remaining"].clip(lower=1).astype(int)
    return f.reset_index(drop=True)


# ------------------------------------------------------- projection

def _logistic(z):
    return 1 / (1 + np.exp(-z))


def hazards(model, mob, band, u) -> np.ndarray:
    """Chapter 18's monthly default hazard for a matrix of months on
    book (accounts x months), each account's band and a path of
    unemployment; zero before the clock starts."""
    c = model.default
    gi = np.minimum(pdm._hazard_group(np.maximum(mob, 1)),
                    max(model.groups))
    gc = np.r_[0.0, [c[f"mob_g{g}"] for g in model.groups[1:]]]
    gmap = np.zeros(max(model.groups) + 1)
    gmap[model.groups] = gc
    bc = {b: c.get(f"band_{b}", 0.0) for b in model.bands}
    bz = np.array([bc.get(x, 0.0) for x in band])
    z = c["const"] + gmap[gi] + bz[:, None] + c["u"] * u[None, :]
    return np.where(mob >= 1, _logistic(z), 0.0)


def exits(model, mob, band) -> np.ndarray:
    """Chapter 18's monthly closure hazard (revolving accounts)."""
    c = model.close
    gi = np.minimum(pdm._hazard_group(np.maximum(mob, 1)),
                    max(model.groups))
    gmap = np.zeros(max(model.groups) + 1)
    gmap[model.groups] = np.r_[0.0, [c[f"mob_g{g}"]
                                     for g in model.groups[1:]]]
    bz = np.array([c.get(f"band_{x}", 0.0) for x in band])
    return _logistic(c["const"] + gmap[gi] + bz[:, None])


def incidence(h, x) -> np.ndarray:
    """Marginal PD each month with closure as a competing exit."""
    alive = np.cumprod(1 - h - x, axis=1)
    alive = np.hstack([np.ones((h.shape[0], 1)), alive[:, :-1]])
    return alive * h


def lift(h, x, target, months: int = 12) -> np.ndarray:
    """Scale each account's first-year hazards so that its 12-month
    PD is `target`; later months keep the band's hazard."""
    lo = np.zeros(len(h))
    hi = np.full(len(h), 200.0)
    for _ in range(40):
        c = (lo + hi) / 2
        hh = np.minimum(h[:, :months] * c[:, None],
                        0.999 - x[:, :months])
        pd12 = incidence(hh, x[:, :months]).sum(axis=1)
        low = pd12 < target
        lo, hi = np.where(low, c, lo), np.where(low, hi, c)
    out = h.copy()
    c = (lo + hi) / 2
    out[:, :months] = np.minimum(h[:, :months] * c[:, None],
                                 0.999 - x[:, :months])
    return out


def balances(balance, rate_pct, remaining, months: int,
             free=None) -> np.ndarray:
    """Scheduled balance at the start of each future month (accounts
    x months), as `loanmath.schedule` would run it: interest added in
    any payment-free months, then level payments that clear the
    balance by maturity, and nothing after maturity."""
    b0 = np.asarray(balance, dtype=float)[:, None]
    r = np.asarray(rate_pct, dtype=float)[:, None] / 1200
    n = np.asarray(remaining, dtype=float)[:, None]
    f = (np.zeros_like(n) if free is None
         else np.asarray(free, dtype=float)[:, None])
    k = np.arange(months)[None, :]
    bf = b0 * (1 + r) ** f                 # after the free months
    j = np.maximum(k - f, 0)
    m = np.maximum(n - f, 1)
    g, gm = (1 + r) ** j, (1 + r) ** m
    safe = np.where(r > 0, r, 1)
    pay = np.where(r > 0, bf * safe * gm / (gm - 1), bf / m)
    bal = np.where(r > 0, bf * g - pay * (g - 1) / safe, bf - pay * j)
    bal = np.where(k < f, b0 * (1 + r) ** k, bal)
    return np.where(k < n, np.maximum(bal, 0), 0.0)


def _lgd(params, product, scenario):
    col = params["scenarios"].loc[scenario, "lgd"]
    return float(params["lgd"].loc[product, col])


def project_retail(book, params, basis="ifrs9") -> pd.DataFrame:
    """12-month and lifetime PD and ECL under each scenario, for every
    retail account (one in default is measured as if it were not, so
    that a forced stage has a number; `run` replaces it)."""
    out = []
    lr = params["long_run_u"]
    for p, g in book.groupby("product"):
        model = params["hazards"][p]
        n = len(g)
        life = g["remaining"].to_numpy()
        H = int(life.max())
        k = np.arange(1, H + 1)
        clock = g["mob"].to_numpy() - FREE_MONTHS.get(p, 0)
        mob = clock[:, None] + k[None, :]
        band = g["band"].to_numpy()
        live = k[None, :] <= life[:, None]
        if p in REVOLVING:
            x = exits(model, mob, band)
            ccf = params["ccf"]["ccf"]
            if p == "card":
                tab = pd.DataFrame({"ccf": list(ccf["card"].values())})
                e0 = eadm.exposure(g.balance_cents, g.limit_cents, tab)
            else:
                e0 = (g.balance_cents + ccf["sme_overdraft"]
                      * (g.limit_cents - g.balance_cents).clip(lower=0))
            e0 = np.asarray(e0, dtype=float)
            ead = np.repeat(e0[:, None], H, axis=1)
            if basis == "cecl":       # no provision on what can be cut
                b = g.balance_cents.to_numpy(dtype=float)[:, None]
                run = (1 - params["card_paydown"]) if p == "card" else 1
                ead = b * run ** (k[None, :] - 1)
        else:
            x = np.full((n, H), params["prepay"][p])
            free = np.maximum(FREE_MONTHS.get(p, 0) - g["age"], 0)
            ead = balances(g.balance_cents, g.rate_pct, life, H, free)
            e0 = ead[:, 0]
        x = np.where(live, x, 0.0)
        df = (1 + g["rate_pct"].to_numpy()[:, None] / 1200) ** -k
        upl = params["uplift"]["uplift"]
        mult = np.array([upl.get((p, q), 1.0) for q in g["pool"]])
        res = {"account_id": g["account_id"].to_numpy(),
               "ead_cents": e0}
        k12 = np.tile(np.arange(1, 13), (n, 1))
        h0 = hazards(model, k12, band, np.full(12, lr))
        x0 = (exits(model, k12, band) if p in REVOLVING
              else np.full((n, 12), params["prepay"][p]))
        res["pd12_orig"] = incidence(h0, x0).sum(axis=1)
        for s, row in params["scenarios"].iterrows():
            u = path(row["path"], H, lr if basis == "cecl" else None)
            h = np.where(live, hazards(model, mob, band, u), 0.0)
            pd12 = incidence(h[:, :12], x[:, :12]).sum(axis=1)
            h = lift(h, x, np.minimum(pd12 * mult, 0.99))
            marg = incidence(h, x)
            loss = marg * ead * df * _lgd(params, p, s)
            res[f"pd12_{s}"] = marg[:, :12].sum(axis=1)
            res[f"pdlife_{s}"] = marg.sum(axis=1)
            res[f"ecl12_{s}"] = loss[:, :12].sum(axis=1)
            res[f"ecllife_{s}"] = loss.sum(axis=1)
        out.append(pd.DataFrame(res))
    return pd.concat(out, ignore_index=True)


def commercial_pd(params, grade, years: int) -> np.ndarray:
    """Each facility's yearly PD, given survival to that year, through
    the cycle: the master scale in year one, then the analysts'
    migration matrix (Chapter 18), held after year five."""
    cp = params["commercial"]
    out = np.zeros((len(grade), years))
    for i, g in enumerate(np.asarray(grade, dtype=int)):
        cum = np.r_[0.0, cp["matrix_cumulative"][str(g)]]
        cond = np.diff(cum) / (1 - cum[:-1])
        cond[0] = cp["master_scale"][str(g)]
        out[i] = np.r_[cond, np.repeat(cond[-1], max(years - 5, 0))
                       ][:years]
    return out


def project_commercial(book, params, basis="ifrs9") -> pd.DataFrame:
    """The commercial facilities, as `project_retail`.

    A year's PD moves with the scenario through the sensitivity of
    small-business term loans to unemployment (Chapter 18), applied
    to the odds, against the decade's average unemployment."""
    g = book
    lr = params["long_run_u"]
    beta = params["hazards"]["sme_term"].default["u"]
    life = g["remaining"].to_numpy()
    H = int(life.max())
    years = (H + 11) // 12
    k = np.arange(1, H + 1)
    live = k[None, :] <= life[:, None]
    ttc = commercial_pd(params, g["grade"], years)
    drawn = g["balance_cents"].to_numpy(dtype=float)[:, None]
    lim = g["limit_cents"].to_numpy(dtype=float)[:, None]
    rev = (g["kind"] == "revolver").to_numpy()[:, None]
    ccf = params["ccf"]["ccf"]["revolver"]
    run = 1 - (k[None, :] - 1) / life[:, None]
    ead = np.where(rev, drawn + ccf * np.maximum(lim - drawn, 0),
                   drawn * np.clip(run, 0, 1))
    df = (1 + g["rate_pct"].to_numpy()[:, None] / 1200) ** -k
    key = np.where(g["secured"], "commercial_secured",
                   "commercial_unsecured")
    res = {"account_id": g["account_id"].to_numpy(),
           "ead_cents": ead[:, 0],
           "pd12_orig": np.array([params["commercial"]["master_scale"]
                                  [str(x)] for x in g["grade0"]])}
    yr = (k - 1) // 12
    for s, row in params["scenarios"].iterrows():
        u = path(row["path"], years * 12,
                 lr if basis == "cecl" else None)
        ubar = u.reshape(years, 12).mean(axis=1)
        odds = ttc / (1 - ttc) * np.exp(beta * (ubar - lr))[None, :]
        annual = odds / (1 + odds)
        h = 1 - (1 - annual[:, yr]) ** (1 / 12)
        h = np.where(live, h, 0.0)
        marg = incidence(h, np.zeros_like(h))
        col = params["scenarios"].loc[s, "lgd"]
        lgd = params["lgd"].loc[key, col].to_numpy()[:, None]
        loss = marg * ead * df * lgd
        res[f"pd12_{s}"] = marg[:, :12].sum(axis=1)
        res[f"pdlife_{s}"] = marg.sum(axis=1)
        res[f"ecl12_{s}"] = loss[:, :12].sum(axis=1)
        res[f"ecllife_{s}"] = loss.sum(axis=1)
    return pd.DataFrame(res)


# ------------------------------------------------------------ staging

def sicr(pd_now, pd_orig, ratio: float = SICR_RATIO,
         points: float = SICR_POINTS) -> np.ndarray:
    """Fernhill's quantitative test of a significant increase in
    credit risk: the 12-month PD now (weighted across scenarios) at
    least `ratio` times the PD when the account was made, and at
    least `points` higher."""
    now, orig = np.asarray(pd_now), np.asarray(pd_orig)
    return (now >= ratio * orig) & (now - orig >= points)


def stage(frame, ratio: float = SICR_RATIO,
          points: float = SICR_POINTS) -> pd.DataFrame:
    """Each account's stage and the first reason that put it there:
    default (3); arrears, cured, watchlist or pd (2); none (1)."""
    f = frame
    reasons = [("default", f["in_default"]),
               ("arrears", f["missed"] >= BACKSTOP_MISSED),
               ("cured", f["cured"]),
               ("watchlist", f["grade"].isin(WATCHLIST)),
               ("pd", sicr(f["pd12"], f["pd12_orig"], ratio, points))]
    reason = np.full(len(f), "", dtype=object)
    for name, cond in reversed(reasons):
        c = pd.Series(cond, index=f.index).fillna(False)
        reason = np.where(c.to_numpy(dtype=bool), name, reason)
    st = np.where(reason == "default", 3, np.where(reason == "", 1, 2))
    return pd.DataFrame({"stage": st, "reason": reason},
                        index=f.index)


# -------------------------------------------------------------- a run

def run(con, as_of=AS_OF, params: dict | None = None,
        basis: str = "ifrs9", stages: pd.Series | None = None,
        ratio: float = SICR_RATIO, points: float = SICR_POINTS
        ) -> pd.DataFrame:
    """The provision on `as_of`, one row per account.

    `basis` is "ifrs9" (stages; 12-month ECL in stage 1, lifetime in
    2 and 3) or "cecl" (lifetime for everything). `stages`, a Series
    by account_id, forces stages (the movement analysis uses it).
    Columns `ecl_<scenario>` are each scenario's provision for the
    account's stage, and `ecl` is their probability-weighted sum.
    """
    if params is None:
        params = parameters(con, as_of)
    w = params["scenarios"]["weight"]
    rb = retail_book(con, as_of)
    cb = commercial_book(con, as_of)
    rb["segment"], cb["segment"] = "retail", "commercial"
    rb["grade"] = np.nan
    cb = cb.rename(columns={"defaulted": "in_default"})
    cb["missed"], cb["cured"] = 0, False
    book = pd.concat([rb, cb], ignore_index=True)
    cb = cb.rename(columns={"in_default": "defaulted"})
    proj = pd.concat([project_retail(rb, params, basis),
                      project_commercial(cb, params, basis)])
    book = book.merge(proj, on="account_id", how="left")
    book["pd12"] = sum(w[s] * book[f"pd12_{s}"] for s in WEIGHTED)
    book["pd_life"] = sum(w[s] * book[f"pdlife_{s}"] for s in WEIGHTED)
    book = pd.concat([book, stage(book, ratio, points)], axis=1)
    if stages is not None:
        forced = book["account_id"].map(stages)
        book["stage"] = forced.fillna(book["stage"]).astype(int)
    d = book["in_default"].fillna(False).to_numpy(dtype=bool)
    book.loc[d, "ead_cents"] = book.loc[d, "balance_cents"]
    book.loc[d, ["pd12", "pd_life"]] = 1.0
    lgd_key = np.where(book["segment"] == "retail", book["product"],
                       np.where(book["secured"].fillna(False),
                                "commercial_secured",
                                "commercial_unsecured"))
    for s in WEIGHTED:
        col = params["scenarios"].loc[s, "lgd"]
        lgd = params["lgd"][col].reindex(lgd_key).to_numpy()
        life = book[f"ecllife_{s}"].to_numpy()
        twelve = book[f"ecl12_{s}"].to_numpy()
        st = book["stage"].to_numpy()
        val = np.where(st == 1, twelve, life)
        if basis == "cecl":
            val = life
        val = np.where(st == 3, book["balance_cents"] * lgd, val)
        book[f"ecl_{s}"] = np.nan_to_num(val)
    book["ecl"] = sum(w[s] * book[f"ecl_{s}"] for s in WEIGHTED)
    book["ecl12"] = sum(w[s] * book[f"ecl12_{s}"].fillna(0)
                        for s in WEIGHTED)
    book["ecl_life"] = sum(w[s] * book[f"ecllife_{s}"].fillna(0)
                           for s in WEIGHTED)
    book.attrs.update(as_of=str(as_of), basis=basis)
    return book


def summary(r: pd.DataFrame, by=("product", "stage"),
            col: str = "ecl") -> pd.DataFrame:
    """Accounts, gross carrying amount, provision and coverage."""
    g = r.groupby(list(by))
    out = pd.DataFrame({"accounts": g.size(),
                        "balance_cents": g["balance_cents"].sum(),
                        "ecl_cents": g[col].sum()})
    out["coverage"] = out["ecl_cents"] / out["balance_cents"]
    return out


# ----------------------------------------------- the provision moves

MOVES = ["opening", "new loans", "repaid or closed", "written off",
         "remeasured in stage", "stage transfers", "parameters",
         "scenarios", "closing"]
WRITTEN_OFF = ("charged_off", "vehicle_repossessed", "property_sold",
               "collateral_sold")


def movement(con, opening: pd.DataFrame, closing: pd.DataFrame,
             params_open: dict, params_close: dict) -> pd.DataFrame:
    """The change in the provision from one run to the next, in the
    order a finance team reports it, for retail, commercial and all.

    Accounts only in the opening run have left the book: written off
    if they ended in a write-off or a commercial default, repaid or
    closed otherwise. Accounts only in the closing run are new. For
    accounts in both, the closing date is run three more times, each
    changing one thing from the opening run: the books as they now
    stand, with the opening stages (remeasured in stage: repayments,
    ageing, new arrears or grades), the stages as they now stand
    (stage transfers), the parameters re-estimated (parameters);
    what is left is the change of scenarios.
    """
    as_of = closing.attrs["as_of"]
    o = opening.set_index("account_id")["ecl"]
    c = closing.set_index("account_id")["ecl"]
    seg = pd.concat([opening.set_index("account_id")["segment"],
                     closing.set_index("account_id")["segment"]])
    seg = seg[~seg.index.duplicated()]
    both = o.index.intersection(c.index)
    gone = o.index.difference(c.index)
    off = {r[0] for r in con.execute(f"""
        SELECT account_id FROM accounts
        WHERE close_reason IN {WRITTEN_OFF}
        UNION SELECT facility_id FROM facility_months
        WHERE status = 'defaulted'""").fetchall()}
    wo = gone[gone.isin(list(off))]
    st0 = opening.set_index("account_id")["stage"]
    st1 = closing.set_index("account_id")["stage"]
    p_mid = dict(params_close, scenarios=params_open["scenarios"])

    def again(params, stages):
        r = run(con, as_of, params, stages=stages)
        return r.set_index("account_id")["ecl"][both]

    a = again(params_open, st0)
    b = again(params_open, st1)
    m = again(p_mid, st1)
    steps = {"opening": o, "new loans": c.drop(both),
             "repaid or closed": -o[gone.difference(wo)],
             "written off": -o[wo],
             "remeasured in stage": a - o[both],
             "stage transfers": b - a, "parameters": m - b,
             "scenarios": c[both] - m, "closing": c}
    out = pd.DataFrame({k: v.groupby(seg.reindex(v.index)).sum()
                        for k, v in steps.items()}).T.fillna(0.0)
    out = out.reindex(columns=["retail", "commercial"], fill_value=0)
    out["all"] = out.sum(axis=1)
    return out.loc[MOVES]


# ------------------------------------------------------------ saving

def save(r: pd.DataFrame, name: str | None = None) -> str:
    """Write a run, one row per account, under data/ballast/ecl/."""
    OUT.mkdir(parents=True, exist_ok=True)
    keep = ["account_id", "segment", "product", "stage", "reason",
            "balance_cents", "limit_cents", "ead_cents", "rate_pct",
            "pd12_orig", "pd12", "pd_life", "ecl12", "ecl_life", "ecl",
            "grade"] + [f"ecl_{s}" for s in WEIGHTED]
    if "cecl" in r:
        keep.append("cecl")
    name = name or f"ecl_{r.attrs['as_of']}.parquet"
    path = OUT / name
    r[keep].to_parquet(path, index=False)
    return str(path.relative_to(BALLAST.parent.parent))


def load(as_of=AS_OF) -> pd.DataFrame:
    """The saved provision by account for `as_of`."""
    if isinstance(as_of, dt.date):
        as_of = as_of.isoformat()
    return pd.read_parquet(OUT / f"ecl_{as_of}.parquet")
