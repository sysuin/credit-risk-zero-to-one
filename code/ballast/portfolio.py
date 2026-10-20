"""Portfolio credit risk: how a whole book's losses are distributed.

A provision is the average year; capital is the bad one. This module
works out how bad, for Fernhill's whole book at once:

- the **Vasicek distribution**: the default rate of a large pool of
  similar loans that share one economy, its quantiles and its
  expected shortfall;
- **correlations from default history**: each segment's yearly
  default rates, by the method of moments and by maximum likelihood
  for a finite pool, with a profile-likelihood interval; the factor
  each year's defaults imply, and how much of it segments share;
- a **Monte Carlo** of the one-year loss: retail pools by product,
  score band and arrears, and every company by name; a factor for
  each retail product and each sector, all loading on one economy;
  loss given default that rises in bad draws; exposures with Chapter
  19's conversion factors;
- **risk measures** (expected loss, VaR, expected shortfall,
  economic capital), each name's and pool's share of the tail, and
  the **concentration** measures: HHI, effective number of names and
  the granularity adjustment.

    import fernhill
    from ballast import capital, portfolio as pf
    con = fernhill.connect()
    pools, names = pf.book(con, capital.load())
    model = pf.Model(rho=..., beta=..., common=...)
    res = pf.simulate(pools, names, model)
    res.var(0.999), res.es(0.999), res.ec(0.999)

Ballast never reads the truth database. Money is in cents.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import brentq, minimize_scalar
from scipy.special import gammaln, ndtr, ndtri
from scipy.stats import norm

from ballast import capital
from ballast import performance as perf
from ballast.config import AS_OF, BALLAST, ROOT, SEED
from ballast.parameters import ead as eadm
from ballast.parameters import lgd as lgdm
from ballast.parameters import pd as pdm

OUT = BALLAST / "portfolio"

# The choices a reviewer will ask about.
CONFIDENCE = 0.999          # the one-in-a-thousand year, as Basel
YEARS = range(2017, 2026)   # yearly default rates: 1 Jan open book
RETAIL = ["personal", "card", "auto", "mortgage", "sme_term",
          "sme_overdraft", "sme_emergency"]
SEGMENTS = RETAIL[:-1] + ["companies"]    # estimated from history
SHARES_FACTOR = {"sme_emergency": "sme_term"}   # too young a cycle
DOWNTURN_YEAR = 0.90        # downturn LGD: a one-in-ten bad year
N_SIMS = 200_000
CHUNK = 10_000
NODES = 2001                # grid over the economy, -8 to 8


# ===================================================== Vasicek

def conditional_pd(p, rho, z):
    """A borrower's PD given the economy z (z < 0 is a bad year)."""
    p, rho = np.asarray(p, float), np.asarray(rho, float)
    return ndtr((ndtri(p) - np.sqrt(rho) * np.asarray(z))
                / np.sqrt(1 - rho))


def vasicek_cdf(x, p, rho):
    """Share of years in which a large pool's default rate <= x."""
    x = np.clip(np.asarray(x, float), 1e-300, 1 - 1e-16)
    rho = np.asarray(rho, float)
    return norm.cdf((np.sqrt(1 - rho) * norm.ppf(x) - norm.ppf(p))
                    / np.sqrt(rho))


def vasicek_quantile(q, p, rho):
    """The default rate a large pool exceeds in a share 1-q of years."""
    rho = np.asarray(rho, float)
    return norm.cdf((norm.ppf(p) + np.sqrt(rho) * norm.ppf(q))
                    / np.sqrt(1 - rho))


def vasicek_pdf(x, p, rho):
    """Density of a large pool's default rate."""
    x = np.asarray(x, float)
    g = norm.ppf(x)
    return np.sqrt((1 - rho) / rho) * np.exp(
        0.5 * g ** 2 - (np.sqrt(1 - rho) * g - norm.ppf(p)) ** 2
        / (2 * rho))


def vasicek_es(q, p, rho, n: int = 2000):
    """Expected shortfall of the default rate: its average in the
    worst share 1-q of years."""
    u = q + (1 - q) * (np.arange(n) + 0.5) / n
    return float(vasicek_quantile(u, p, rho).mean())


def vasicek_variance(p, rho) -> float:
    """Variance of a large pool's default rate."""
    if rho <= 0:
        return 0.0
    x = np.linspace(-9, 9, 4001)
    w = norm.pdf(x) * (x[1] - x[0])
    c = conditional_pd(p, rho, x)
    return float((w * c ** 2).sum() - ((w * c).sum()) ** 2)


# ============================================ default history

def default_history(con, years=YEARS) -> pd.DataFrame:
    """Every segment's yearly default rate: retail products by
    Chapter 6's measure (accounts open and not in default on 1
    January, a new default under the 2021 definition in the year);
    companies by clients with a performing facility at the year end
    before, defaulting in the year."""
    eps = perf.default_episodes(con, pdm.DEFINITION)
    r = pdm.annual_default_rates(con, eps, RETAIL, years)
    c = con.execute("""
        WITH alive AS (
            SELECT DISTINCT f.company_id, year(m.month) + 1 AS year
            FROM facility_months m JOIN facilities f
              USING (facility_id)
            WHERE month(m.month) = 12 AND m.status = 'performing')
        SELECT a.year, 'companies' AS product,
               count(*) AS at_risk, count(d.company_id) AS defaults
        FROM alive a LEFT JOIN corporate_defaults d
          ON d.company_id = a.company_id
         AND year(d.default_month) = a.year
        WHERE a.year BETWEEN ? AND ?
        GROUP BY 1 ORDER BY 1""", [min(years), max(years)]).df()
    c["rate"] = c.defaults / c.at_risk
    out = pd.concat([r, c], ignore_index=True)
    out = out.rename(columns={"product": "segment"})
    out = out[out.at_risk > 0].astype({"at_risk": int,
                                       "defaults": int})
    return out.sort_values(["segment", "year"]).reset_index(drop=True)


def mom_rho(rate, at_risk) -> float:
    """Method of moments: the correlation whose Vasicek variance
    equals the yearly rates' variance, less the variance a binomial
    pool of that size would show with no correlation at all."""
    r, n = np.asarray(rate, float), np.asarray(at_risk, float)
    target = r.var(ddof=1) - np.mean(r * (1 - r) / n)
    p = r.mean()
    if target <= 0:
        return 0.0
    f = lambda rho: vasicek_variance(p, rho) - target  # noqa: E731
    if f(0.999) < 0:
        return 0.999
    return brentq(f, 1e-6, 0.999)


# A fine grid, not Gauss-Hermite: with thousands of loans a year the
# likelihood of a year's count is a narrow spike in the economy.
_X = np.linspace(-8, 8, NODES)
_W = norm.pdf(_X) / norm.pdf(_X).sum()


def _log_binom(d, n, pz):
    pz = np.clip(pz, 1e-15, 1 - 1e-15)
    return (gammaln(n + 1) - gammaln(d + 1) - gammaln(n - d + 1)
            + d * np.log(pz) + (n - d) * np.log1p(-pz))


def loglik(p, rho, defaults, at_risk, trend: float = 0.0) -> float:
    """Log likelihood of yearly default counts in a finite pool: each
    year's economy drawn afresh, defaults binomial given it. With a
    `trend`, the default threshold drifts by that much a year (a
    book whose quality changes)."""
    d = np.asarray(defaults, float)
    n = np.asarray(at_risk, float)
    t = np.arange(len(d)) - (len(d) - 1) / 2
    c = norm.ppf(p) + trend * t
    pz = ndtr((c[None, :] - np.sqrt(rho) * _X[:, None])
              / np.sqrt(1 - rho))
    ll = _log_binom(d[None, :], n[None, :], pz)
    m = ll.max(axis=0)
    return float((m + np.log((_W[:, None] * np.exp(ll - m)).sum(0)))
                 .sum())


def _profile(rho, d, n, trend: bool):
    """Best log likelihood at a given correlation, and its p (and
    trend, a year's drift in the threshold)."""
    def best_c(b):
        r = minimize_scalar(
            lambda c: -loglik(ndtr(c), rho, d, n, b),
            bounds=(-5, 0), method="bounded",
            options={"xatol": 1e-6})
        return -r.fun, float(r.x)

    if not trend:
        ll, c = best_c(0.0)
        return ll, float(ndtr(c)), 0.0
    r = minimize_scalar(lambda b: -best_c(b)[0], bounds=(-0.3, 0.3),
                        method="bounded", options={"xatol": 1e-5})
    ll, c = best_c(float(r.x))
    return ll, float(ndtr(c)), float(r.x)


def fit_rho(defaults, at_risk, trend: bool = False,
            level: float = 0.90, hi: float = 0.5) -> dict:
    """Maximum likelihood correlation and PD for a finite pool, with
    a profile-likelihood interval at `level`: the correlations whose
    likelihood is within the chi-squared cut of the best."""
    d = np.asarray(defaults, float)
    n = np.asarray(at_risk, float)
    prof = lambda r: _profile(r, d, n, trend)[0]  # noqa: E731
    grid = np.geomspace(1e-5, hi, 41)
    ll = np.array([prof(g) for g in grid])
    i = int(ll.argmax())
    a, b = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    r = minimize_scalar(lambda x: -prof(x), bounds=(a, b),
                        method="bounded", options={"xatol": 1e-6})
    rho = float(r.x) if -r.fun >= ll[i] else float(grid[i])
    best, p, drift = _profile(rho, d, n, trend)
    cut = best - 0.5 * norm.ppf(0.5 + level / 2) ** 2
    g = lambda x: prof(x) - cut  # noqa: E731
    below = np.nonzero((ll < cut) & (grid < rho))[0]
    above = np.nonzero((ll < cut) & (grid > rho))[0]
    lo = (grid[0] if len(below) == 0 else
          brentq(g, grid[below[-1]], rho, xtol=1e-6))
    up = (hi if len(above) == 0 else
          brentq(g, rho, grid[above[0]], xtol=1e-6))
    return {"p": p, "rho": rho, "lo": float(lo), "hi": float(up),
            "trend": drift, "loglik": best}


def implied_factor(defaults, at_risk, p, rho) -> np.ndarray:
    """Each year's economy as its defaults imply it: the average of z
    given the year's count (negative in a bad year)."""
    d = np.asarray(defaults, float)[None, :]
    n = np.asarray(at_risk, float)[None, :]
    pz = conditional_pd(p, rho, _X)[:, None]
    ll = _log_binom(d, n, pz)
    w = _W[:, None] * np.exp(ll - ll.max(axis=0))
    return (w * _X[:, None]).sum(0) / w.sum(0)


def loadings(factors: pd.DataFrame) -> pd.Series:
    """How much of each segment's factor is one shared economy: the
    first principal component of the factors' correlations, so that
    corr(i, j) is about loading_i x loading_j. Returned squared (the
    share of variance shared), between 0 and 1."""
    c = factors.corr().to_numpy()
    vals, vecs = np.linalg.eigh(c)
    v = vecs[:, -1] * np.sqrt(vals[-1])
    v = v if v.sum() >= 0 else -v
    return pd.Series(np.clip(v, 0, 1) ** 2, index=factors.columns)


def regulatory_rho(r: pd.DataFrame) -> pd.Series:
    """The correlations Chapter 21's formula gave each segment,
    weighted by IRB EAD, performing exposures."""
    x = r[~r.in_default.astype(bool)].copy()
    x["rho"] = capital.correlation(x.pd_floored, x.cls, x.sales_m)
    x["segment"] = np.where(x.segment == "commercial", "companies",
                            x["product"])
    g = x.assign(w=x.rho * x.irb_ead).groupby("segment")
    return g.w.sum() / g.irb_ead.sum()


def asset_correlations(panel: pd.DataFrame, sectors: dict,
                       min_months: int = 36) -> dict:
    """Average pairwise correlation of listed clients' monthly asset
    returns (Chapter 17's Merton values), within and across sectors.
    Months in which a company's accounts changed are left out: the
    default point moves then, not the assets."""
    p = panel.sort_values(["company_id", "month"]).copy()
    p["ret"] = p.groupby("company_id")["assets"].transform(
        lambda s: np.log(s).diff())
    same = p.groupby("company_id").fiscal_year.diff() == 0
    x = p[same].pivot(index="month", columns="company_id",
                      values="ret")
    c = x.corr(min_periods=min_months).to_numpy()
    s = np.array([sectors[i] for i in x.columns])
    up = np.triu(np.ones(c.shape, bool), 1) & ~np.isnan(c)
    within = c[up & (s[:, None] == s[None, :])]
    across = c[up & (s[:, None] != s[None, :])]
    return {"companies": len(x.columns), "within": float(within.mean()),
            "across": float(across.mean()), "pairs_within": len(within),
            "pairs_across": len(across)}


def estimate(con, r: pd.DataFrame | None = None,
             history: pd.DataFrame | None = None) -> dict:
    """Every segment's correlation from its default history: the
    method of moments; maximum likelihood with its 90% interval;
    the same without 2020; with a drifting book; and the rules'
    correlation from Chapter 21's saved run, for comparison."""
    h = default_history(con) if history is None else history
    reg = regulatory_rho(capital.load() if r is None else r)
    out = {}
    for seg in SEGMENTS:
        g = h[h.segment == seg]
        calm = g[g.year != 2020]
        fit = fit_rho(g.defaults, g.at_risk)
        out[seg] = {**fit, "mom": mom_rho(g.rate, g.at_risk),
                    "no2020": fit_rho(calm.defaults,
                                      calm.at_risk)["rho"],
                    "drift": fit_rho(g.defaults, g.at_risk,
                                     trend=True)["rho"],
                    "rules": float(reg[seg])}
    return out


def factor_history(history: pd.DataFrame, est: dict) -> pd.DataFrame:
    """The economy each year's defaults imply, by segment."""
    return pd.DataFrame({
        s: pd.Series(implied_factor(g.defaults, g.at_risk,
                                    est[s]["p"], est[s]["rho"]),
                     index=g.year.to_numpy())
        for s, g in history.groupby("segment")
        if s in est})[[s for s in SEGMENTS if s in est]]


def shared(con, est: dict, history: pd.DataFrame | None = None
           ) -> dict:
    """How much the segments share: each one's loading on the economy
    (from the factors its defaults imply) and, from listed clients'
    asset returns, the share of a sector's factor common to all
    companies."""
    from ballast import market as mk
    h = default_history(con) if history is None else history
    beta = loadings(factor_history(h, est))
    sectors = dict(con.execute(
        "SELECT company_id, sector FROM companies").fetchall())
    a = asset_correlations(mk.merton_panel(con), sectors)
    common = min(1.0, a["across"] / a["within"])
    return {"beta": {k: float(v) for k, v in beta.items()},
            "common": common, **a}


def save_json(obj, name: str) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(obj, indent=1, sort_keys=True))
    return str(path.relative_to(ROOT))


def load_json(name: str):
    return json.loads((OUT / name).read_text())


# ==================================================== the book

def book(con, r: pd.DataFrame | None = None,
         revolver_ccf: float | None = None) -> tuple:
    """What the simulation needs from Chapter 21's saved run.

    Retail: performing accounts pooled by product, score band and
    payments missed, with EAD (Chapter 19's conversion factors), the
    EAD-weighted through-the-cycle PD, the effective number of
    exposures, and Chapter 19's LGD, downturn LGD and cure rate.
    Companies: one row per company, its grade's PD, EAD with Fernhill's
    own revolver CCF, and LGD from Fernhill's own workouts (secured
    or not), weighted by EAD. Exposures already in default are left
    out: their loss has happened and is provided for."""
    r = capital.load() if r is None else r
    r = r[~r.in_default.astype(bool)]
    lg = lgdm.load()["products"]
    ret = r[r.segment == "retail"].copy()
    ret["missed"] = ret.missed.clip(upper=2)
    ret["e"] = ret.irb_ead
    ret["pe"] = ret["pd"] * ret.e
    ret["e2"] = ret.e ** 2
    pools = ret.groupby(["product", "band", "missed"]).agg(
        accounts=("account_id", "size"), ead=("e", "sum"),
        pe=("pe", "sum"), e2=("e2", "sum")).reset_index()
    pools["pd"] = pools.pe / pools.ead
    pools["n_eff"] = np.maximum(1, np.round(pools.ead ** 2 / pools.e2))
    for k in ("lgd", "downturn", "cure_rate"):
        pools[k] = pools["product"].map(
            {p: v[k] for p, v in lg.items()})
    pools["segment"] = pools["product"]
    pools = pools.drop(columns=["pe", "e2"])

    com = r[r.segment == "commercial"].copy()
    ccf = eadm.load()["ccf"]["revolver"] if revolver_ccf is None \
        else revolver_ccf
    com["e"] = capital.irb_ead(com, revolver_ccf=ccf)
    own = commercial_lgd(con)
    com["lgd_own"] = np.where(com.secured.astype(bool), own[True],
                              own[False])
    com["lw"] = com.lgd_own * com.e
    sec = dict(con.execute(
        "SELECT company_id, sector FROM companies").fetchall())
    names = com.groupby("company_id").agg(
        grade=("grade", "first"), pd=("pd", "first"), ead=("e", "sum"),
        drawn=("drawn_cents", "sum"), lw=("lw", "sum"),
        facilities=("account_id", "size")).reset_index()
    names["lgd"] = names["lw"] / names.ead
    names["sector"] = names.company_id.map(sec)
    names["segment"] = "companies"
    return pools, names.drop(columns="lw")


def commercial_lgd(con) -> dict:
    """Fernhill's own commercial LGD, secured and unsecured (Chapter
    20's workouts, weighted by exposure)."""
    from ballast import ecl
    w = ecl.commercial_lgd(con)
    return {bool(k): float((g.lgd * g.ead_cents).sum()
                           / g.ead_cents.sum())
            for k, g in w.groupby("secured")}


def expected_loss(pools: pd.DataFrame, names: pd.DataFrame) -> float:
    """The analytic expected loss, PD x LGD x EAD summed (cents)."""
    return float((pools.pd * pools.lgd * pools.ead).sum()
                 + (names.pd * names.lgd * names.ead).sum())


def hhi(x) -> float:
    """Herfindahl-Hirschman index: the sum of squared shares."""
    s = np.asarray(x, float)
    s = s / s.sum()
    return float((s ** 2).sum())


def effective_number(x) -> float:
    """How many equal exposures would be as concentrated: 1 / HHI."""
    return 1 / hhi(x)


# ===================================================== the model

def lgd_in_draw(lgd, downturn, y, tail=DOWNTURN_YEAR):
    """Retail LGD in a draw of its factor y: the long-run LGD in an
    average year, the downturn LGD in a one-in-ten bad year, and
    along a straight line between and beyond (clipped to 0-1)."""
    s = (np.asarray(downturn) - np.asarray(lgd)) / norm.ppf(tail)
    return np.clip(np.asarray(lgd) - s * np.asarray(y), 0, 1)


def frye_jacobs(p, lgd, rho, z=None, dr=None):
    """LGD given the economy z by Frye and Jacobs' rule: the expected
    loss rate is a Vasicek quantile of the same economy, with the
    long-run PD x LGD as its average. Needs no downturn estimate.
    Pass `dr`, the conditional PD, if it is already known."""
    p, lgd = np.asarray(p, float), np.asarray(lgd, float)
    k = (ndtri(p) - ndtri(p * lgd)) / np.sqrt(1 - rho)
    dr = conditional_pd(p, rho, z) if dr is None else dr
    dr = np.clip(dr, 1e-300, 1)
    return ndtr(ndtri(dr) - k) / dr


@dataclass
class Model:
    """Correlations and factor loadings for the simulation.

    `rho`: each segment's asset correlation (within the segment, or
    for companies within a sector). `beta`: the share of each
    segment's factor that is the shared economy. `common`: the share
    of a sector's factor that all companies share (the economy's part
    included); 1 means sectors add nothing of their own."""
    rho: dict
    beta: dict
    common: float = 1.0
    lgd_link: bool = True
    name: str = ""

    def of(self, seg: str) -> tuple:
        k = SHARES_FACTOR.get(seg, seg)
        return self.rho[k], self.beta[k]


def model_from(est: dict, factors: dict, which: str = "rho",
               name: str = "") -> Model:
    """A Model from the saved estimates: each segment's correlation
    (`which` is "rho" for the MLE, "hi" for the top of its interval,
    "rules" for Chapter 21's), the shared loadings and `common`."""
    return Model(rho={s: max(v[which], 1e-6) for s, v in est.items()},
                 beta=dict(factors["beta"]), common=factors["common"],
                 name=name or which)


def with_sectors(model: Model, names: pd.DataFrame, common: float,
                 name: str = "") -> Model:
    """The same model with sectors that have cycles of their own:
    only `common` of a sector's factor is shared with other sectors,
    and the correlation within a sector is raised so that the
    average correlation between two companies stays where the
    default history put it."""
    h = float(((names.sector.value_counts() / len(names)) ** 2).sum())
    rho = model.rho["companies"] / (common + (1 - common) * h)
    return Model(rho={**model.rho, "companies": rho}, beta=model.beta,
                 common=common, lgd_link=model.lgd_link,
                 name=name or model.name)


@dataclass
class Result:
    """One simulation: losses per year drawn (cents)."""
    total: np.ndarray
    fine: np.ndarray                 # idiosyncratic risk averaged out
    by_segment: pd.DataFrame         # years x segment
    pool_loss: np.ndarray            # years x pools (float32)
    name_hits: tuple                 # (year, name, loss) of defaults
    n_names: int
    extra: np.ndarray | None = None  # years x extra names
    extra_fine: np.ndarray | None = None  # their PD x loss each year
    meta: dict = field(default_factory=dict)

    def el(self) -> float:
        return float(self.total.mean())

    def var(self, q=CONFIDENCE, x=None) -> float:
        return float(np.quantile(self.total if x is None else x, q))

    def var_interval(self, q=CONFIDENCE, level=0.95, x=None) -> tuple:
        """A distribution-free interval for the simulated quantile:
        the order statistics the true quantile lies between with
        probability `level` (the simulation's own noise)."""
        x = np.sort(self.total if x is None else x)
        n = len(x)
        half = norm.ppf(0.5 + level / 2) * np.sqrt(n * q * (1 - q))
        lo, hi = int(np.floor(n * q - half)), int(np.ceil(n * q + half))
        return float(x[max(lo, 0)]), float(x[min(hi, n - 1)])

    def es(self, q=CONFIDENCE, x=None) -> float:
        x = self.total if x is None else x
        return float(x[x >= np.quantile(x, q)].mean())

    def ec(self, q=CONFIDENCE, x=None) -> float:
        """Economic capital: the loss in the bad year, less the loss
        expected (which prices and provisions cover)."""
        x = self.total if x is None else x
        return self.var(q, x) - float(x.mean())

    def tail(self, q=CONFIDENCE) -> np.ndarray:
        return self.total >= np.quantile(self.total, q)

    def contributions(self, q=CONFIDENCE) -> tuple:
        """Each pool's and each name's average loss in the years worse
        than the q quantile: they add up to the expected shortfall."""
        t = self.tail(q)
        pools = self.pool_loss[t].astype(float).mean(0)
        yr, nm, ls = self.name_hits
        keep = t[yr]
        names = np.bincount(nm[keep], ls[keep], self.n_names) / t.sum()
        return pools, names


def simulate(pools: pd.DataFrame, names: pd.DataFrame, model: Model,
             n: int = N_SIMS, seed: int = SEED, chunk: int = CHUNK,
             extra: pd.DataFrame | None = None) -> Result:
    """Draw `n` years of the book's one-year loss.

    Each year draws the economy Z, a factor C that all companies
    share beyond it, a factor for each retail product and one for each
    sector. A retail product's factor is sqrt(beta) Z + sqrt(1 - beta)
    times its own; a sector's is sqrt(beta) Z + sqrt(common - beta) C
    + sqrt(1 - common) times its own. Given its factor, a retail pool
    has binomial defaults among its effective number of exposures,
    binomial cures among those, and LGD from `lgd_in_draw`; each
    company defaults with its PD given its sector's factor, and loses
    its LGD moved by Frye and Jacobs' rule. `extra` names (same
    columns as `names`, sectors among theirs) come from their own
    stream and are reported apart, so the book's draws are the same
    with or without them."""
    # Separate streams for the factors, the retail pools, the
    # companies and any extra names, so that changing one part of the
    # book or the model leaves the other parts' draws as they were.
    rng = np.random.default_rng(seed)
    prng = np.random.default_rng([seed, 2])
    crng = np.random.default_rng([seed, 3])
    xrng = np.random.default_rng([seed, 1])
    psegs = sorted({SHARES_FACTOR.get(s, s) for s in pools.segment})
    sectors = sorted(set(names.sector))
    pi = [psegs.index(SHARES_FACTOR.get(s, s)) for s in pools.segment]
    prho = np.array([model.of(s)[0] for s in pools.segment])
    pbeta = np.array([model.of(s)[1] for s in psegs])
    crho, cbeta = model.of("companies")
    common = max(model.common, cbeta)
    nn = pools.n_eff.to_numpy().astype(int)
    unit = pools.ead.to_numpy() / nn
    nc_lgd = (pools.lgd / (1 - pools.cure_rate)).to_numpy()
    nc_dt = (pools.downturn / (1 - pools.cure_rate)).to_numpy()
    cure = pools.cure_rate.to_numpy()
    segs = sorted(set(pools.segment))
    onehot = (pools.segment.to_numpy()[:, None]
              == np.array(segs)[None, :]).astype(float)

    def companies(frame, s_by_sector, gen):
        s = s_by_sector[:, frame.sector.map(sectors.index).to_numpy()]
        p = frame.pd.to_numpy()
        cp = conditional_pd(p, crho, s)
        lg = frame.lgd.to_numpy()
        if model.lgd_link:
            lg = np.clip(frye_jacobs(p, lg, crho, dr=cp), 0, 1)
        loss = frame.ead.to_numpy() * lg
        hit = gen.random(cp.shape) < cp
        return np.where(hit, loss, 0.0), loss * cp

    tot, fin, seg, pl, hits, ext = [], [], [], [], [], []
    done = 0
    while done < n:
        m = min(chunk, n - done)
        z = rng.standard_normal(m)
        c = rng.standard_normal(m)
        own = rng.standard_normal((m, len(psegs)))
        y = (np.sqrt(pbeta) * z[:, None] + np.sqrt(1 - pbeta) * own)
        y = y[:, pi]
        eta = rng.standard_normal((m, len(sectors)))
        s = (np.sqrt(cbeta) * z[:, None]
             + np.sqrt(common - cbeta) * c[:, None]
             + np.sqrt(1 - common) * eta)
        p = conditional_pd(pools.pd.to_numpy(), prho, y)
        d = prng.binomial(nn, p)
        nc = prng.binomial(d, 1 - cure)
        lg = (lgd_in_draw(nc_lgd, nc_dt, y) if model.lgd_link
              else np.broadcast_to(np.clip(nc_lgd, 0, 1), y.shape))
        ploss = nc * unit * lg
        pfine = (p * (1 - cure) * nn * unit * lg).sum(1)
        closs, cfine = companies(names, s, crng)
        if extra is not None:
            ext.append(companies(extra, s, xrng))
        yr, nm = np.nonzero(closs)
        hits.append((yr + done, nm, closs[yr, nm]))
        seg.append(np.column_stack([ploss @ onehot, closs.sum(1)]))
        tot.append(ploss.sum(1) + closs.sum(1))
        fin.append(pfine + cfine.sum(1))
        pl.append(ploss.astype(np.float32))
        done += m
    h = tuple(np.concatenate([x[i] for x in hits]) for i in range(3))
    return Result(
        total=np.concatenate(tot), fine=np.concatenate(fin),
        by_segment=pd.DataFrame(np.vstack(seg),
                                columns=segs + ["companies"]),
        pool_loss=np.vstack(pl), name_hits=h, n_names=len(names),
        extra=np.vstack([e[0] for e in ext]) if ext else None,
        extra_fine=np.vstack([e[1] for e in ext]) if ext else None,
        meta={"n": n, "seed": seed, "model": model.name})


# ====================================== one factor, by formula

def asrf_capital(ead, lgd, p, rho, q=CONFIDENCE) -> float:
    """Chapter 21's formula without its maturity adjustment: the loss
    in the economy's q-quantile year less the expected loss, summed,
    for exposures each a sliver of an infinite pool (cents)."""
    e, l, p_ = (np.asarray(v, float) for v in (ead, lgd, p))  # noqa: E741
    return float((e * l * (vasicek_quantile(q, p_, rho) - p_)).sum())


def one_factor_loss(pools: pd.DataFrame, names: pd.DataFrame,
                    model: Model, q=CONFIDENCE) -> float:
    """The book's loss in the economy's q-quantile year if every
    segment's factor were the economy itself and every exposure a
    sliver: no diversification between segments, no lumps; LGD as
    the model moves it (cents)."""
    z = -norm.ppf(q)
    prho = np.array([model.of(s)[0] for s in pools.segment])
    p = conditional_pd(pools.pd, prho, z)
    nc = pools.lgd / (1 - pools.cure_rate)
    lg = (lgd_in_draw(nc, pools.downturn / (1 - pools.cure_rate), z)
          if model.lgd_link else np.clip(nc, 0, 1))
    retail = (pools.ead * (1 - pools.cure_rate) * lg * p).sum()
    crho = model.of("companies")[0]
    cp = conditional_pd(names.pd, crho, z)
    cl = (np.clip(frye_jacobs(names.pd, names.lgd, crho, dr=cp), 0, 1)
          if model.lgd_link else names.lgd)
    return float(retail + (names.ead * cl * cp).sum())


# ================================================== granularity

def granularity_adjustment(ead, lgd, p, rho, q=CONFIDENCE,
                           h: float = 1e-3) -> float:
    """Gordy's first-order granularity adjustment for one factor:
    what a finite number of names adds to the quantile of a
    portfolio whose idiosyncratic risk had averaged away (cents)."""
    e, l, pd_ = (np.asarray(v, float) for v in (ead, lgd, p))  # noqa: E741

    def mu(y):          # expected loss given a bad economy y = -z
        return (e * l * conditional_pd(pd_, rho, -y)).sum()

    def sig2(y):        # variance of the loss given y
        c = conditional_pd(pd_, rho, -y)
        return (e ** 2 * l ** 2 * c * (1 - c)).sum()

    def g(y):
        dmu = (mu(y + h) - mu(y - h)) / (2 * h)
        return norm.pdf(y) * sig2(y) / dmu

    y = norm.ppf(q)
    return float(-(g(y + h) - g(y - h)) / (2 * h) / (2 * norm.pdf(y)))


# ===================================================== a run

QUANTILES = [0.5, 0.75, 0.9, 0.95, 0.99, 0.995, 0.999, 0.9995]


def run(con, n: int = N_SIMS, seed: int = SEED) -> dict:
    """Everything, from the loan book: correlations, loadings, the
    book on AS_OF, and the simulation under the central model."""
    r = capital.load()
    h = default_history(con)
    est = estimate(con, r, h)
    fac = shared(con, est, h)
    pools, names = book(con, r)
    model = model_from(est, fac, "rho", "central")
    res = simulate(pools, names, model, n=n, seed=seed)
    return {"estimates": est, "factors": fac, "pools": pools,
            "names": names, "model": model, "result": res}


def summarise(run_: dict, as_of=AS_OF) -> tuple:
    """The loss distribution's summary, for Chapters 26 and 27, and
    every pool's and name's share of the tail."""
    res, pools, names = run_["result"], run_["pools"], run_["names"]
    m = run_["model"]
    t = res.tail()
    seg = {s: {"el": float(res.by_segment[s].mean()),
               "alone_999": float(res.by_segment[s].quantile(0.999)),
               "es_999": float(res.by_segment[s][t].mean())}
           for s in res.by_segment.columns}
    summary = {
        "as_of": str(as_of), "units": "cents", "years": len(res.total),
        "seed": res.meta["seed"], "confidence": CONFIDENCE,
        "el": res.el(), "el_formula": expected_loss(pools, names),
        "sd": float(res.total.std()), "worst": float(res.total.max()),
        "quantiles": {str(q): res.var(q) for q in QUANTILES},
        "es": {str(q): res.es(q) for q in (0.99, 0.995, 0.999)},
        "ec_999": res.ec(), "fine_999": res.var(x=res.fine),
        "by_segment": seg, "rho": m.rho, "beta": m.beta,
        "common": m.common, "lgd_link": m.lgd_link,
        "exposures": {"pools": int(len(pools)),
                      "accounts": int(pools.accounts.sum()),
                      "companies": int(len(names)),
                      "ead_retail": float(pools.ead.sum()),
                      "ead_companies": float(names.ead.sum())}}
    pc, nc = res.contributions()
    rows = pd.concat([
        pd.DataFrame({"kind": "pool", "id": pools["product"] + " "
                      + pools.band + " " + pools.missed.astype(str),
                      "segment": pools.segment, "sector": "",
                      "ead": pools.ead,
                      "el": pools["pd"] * pools.lgd * pools.ead,
                      "es_999": pc}),
        pd.DataFrame({"kind": "name", "id": names.company_id,
                      "segment": "companies", "sector": names.sector,
                      "ead": names.ead,
                      "el": names["pd"] * names.lgd * names.ead,
                      "es_999": nc})], ignore_index=True)
    return summary, rows


# ======================================================== saving

def save(summary: dict, contributions: pd.DataFrame,
         as_of=AS_OF) -> list[str]:
    """Write the loss distribution's summary (JSON) and each name's
    and pool's share of it (CSV) under data/ballast/portfolio/."""
    OUT.mkdir(parents=True, exist_ok=True)
    js = OUT / f"loss_{as_of}.json"
    js.write_text(json.dumps(summary, indent=1, sort_keys=True))
    cs = OUT / f"contributions_{as_of}.csv"
    contributions.to_csv(cs, index=False)
    return [str(x.relative_to(ROOT)) for x in (js, cs)]


def load(as_of=AS_OF) -> dict:
    """The summary saved by `save`."""
    return json.loads((OUT / f"loss_{as_of}.json").read_text())


def load_contributions(as_of=AS_OF) -> pd.DataFrame:
    return pd.read_csv(OUT / f"contributions_{as_of}.csv")
