"""Regulatory capital: risk-weighted assets under the standardised and
internal ratings-based (IRB) approaches, the output floor, and the
capital ratios they give Fernhill.

A bank's minimum capital is a share of its **risk-weighted assets**
(RWA): each exposure times a risk weight. This module computes both
ways of setting the weights, account by account, for Fernhill's
retail and small-business accounts and its commercial facilities:

- **standardised**: a simplified version of the standardised rules,
  with risk weights by exposure class (retail, residential mortgage
  by loan-to-value, companies by agency rating or unrated, small and
  medium-sized companies, defaulted exposures) and conversion factors
  for undrawn limits. The real tables, with their conditions, are in
  Appendix C; the simplifications are named where they are made;
- **IRB**: the asymptotic single risk factor formula, with the asset
  correlation of each exposure class, the maturity adjustment for
  companies, floors on PD and LGD, and a scaling factor that is a
  parameter because jurisdictions differ on it. Retail accounts use
  Ballast's own through-the-cycle PD (Chapter 18), downturn LGD and
  EAD (Chapter 19); companies use the foundation approach: their
  grade's PD with a supervisory LGD and conversion factor;
- the **output floor**, expected loss against provisions, the
  capital ratios, buffers and the leverage ratio.

    import fernhill
    from ballast import capital
    con = fernhill.connect()
    b = capital.book(con)                    # one row per exposure
    b["pd"] = capital.ttc_pd(con, b)
    r = capital.irb(capital.standardised(b, capital.provisions()))

Operational and market risk RWA are not computed here: they come from
Fernhill's finance team, in the `bank_capital` table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from ballast import performance as perf
from ballast.commercial.rating import MASTER_SCALE
from ballast.config import AS_OF, BALLAST, ROOT
from ballast.parameters import ead as eadm
from ballast.parameters import lgd as lgdm
from ballast.parameters import pd as pdm

OUT = BALLAST / "capital"

# ------------------------------------- the standardised approach
# A simplified version of the standardised rules (Appendix C has
# the real tables and the conditions an exposure must meet).
RETAIL_RW = 0.75                     # regulatory retail
LTV_EDGES = [0.50, 0.60, 0.80, 0.90, 1.00]
LTV_RW = [0.20, 0.25, 0.30, 0.40, 0.50, 0.70]   # residential mortgage
RATING_RW = {"AAA": 0.20, "AA": 0.20, "A": 0.50, "BBB": 0.75,
             "BB": 1.00, "B": 1.50, "CCC": 1.50}
UNRATED_RW = 1.00                    # a company without a rating
SME_RW = 0.85                        # ... that is small or medium
DEFAULTED_RW = 1.50                  # provisions under 20% of it
DEFAULTED_COVERED_RW = 1.00          # provisions of 20% or more
DEFAULTED_MORTGAGE_RW = 1.00
COVERED = 0.20
SA_CCF = {"card": 0.10, "sme_overdraft": 0.10,     # cancellable
          "commercial_revolver": 0.40}             # committed
GUARANTEED = {"sme_emergency": 0.80}  # the government's share
SME_SALES_M = 50.0                   # small or medium: sales below
RETAIL_LIMIT_CENTS = 100_000_000     # retail: under $1m to a firm

# ----------------------------------------------- the IRB approach
CONFIDENCE = 0.999
SCALING = 1.0                        # 1.06 under Basel II; varies
PD_FLOOR = 0.0005                    # final Basel standard
QRRE_PD_FLOOR = 0.0010               # revolving retail
LGD_FLOOR = {"mortgage": 0.05, "qrre": 0.50,
             "unsecured": 0.30, "secured": 0.15}
MORTGAGE_LGD_FLOOR = 0.10            # the supervisor's letter
FIRB_LGD = 0.40                      # senior unsecured, companies
FIRB_CCF = 0.40                      # committed, undrawn
MATURITY = (1.0, 5.0)                # years, companies
CLASS = {"mortgage": "mortgage", "card": "qrre",
         "personal": "other_retail", "auto": "other_retail",
         "sme_term": "other_retail", "sme_overdraft": "other_retail",
         "sme_emergency": "other_retail",
         "commercial_term": "corporate",
         "commercial_revolver": "corporate"}
SECURED = {"mortgage", "auto"}        # by the home or the car
NEW_CLIENT_GRADE = 6                 # a company not yet reviewed

# ------------------------------------------- the whole bank
OUTPUT_FLOOR = 0.725                 # final Basel standard
MINIMUM = {"cet1": 0.045, "tier1": 0.060, "total": 0.080}
CONSERVATION = 0.025
COUNTERCYCLICAL = 0.010              # illustrative: set nationally
LEVERAGE_MIN = 0.03
EXCESS_CAP = 0.006                   # of credit RWA, into Tier 2


# ======================================================= formulas

def sa_mortgage_rw(ltv) -> np.ndarray:
    """Residential mortgage risk weight by loan-to-value band."""
    i = np.searchsorted(LTV_EDGES, np.asarray(ltv, dtype=float),
                        side="left")
    return np.asarray(LTV_RW)[i]


def sa_corporate_rw(rating, sales_m) -> np.ndarray:
    """A company's weight: its agency letter if it has one, else
    unrated, with the lower weight for small and medium firms."""
    r = pd.Series(np.asarray(rating, dtype=object))
    s = np.asarray(sales_m, dtype=float)
    unrated = np.where(s < SME_SALES_M, SME_RW, UNRATED_RW)
    return r.map(RATING_RW).fillna(pd.Series(unrated)).to_numpy()


def correlation(pd_, cls, sales_m=np.nan) -> np.ndarray:
    """Asset correlation by exposure class (the Basel formulas)."""
    p = np.asarray(pd_, dtype=float)
    c = np.broadcast_to(np.asarray(cls, dtype=object), p.shape)
    s = np.broadcast_to(np.asarray(sales_m, dtype=float), p.shape)
    w50 = (1 - np.exp(-50 * p)) / (1 - np.exp(-50))
    w35 = (1 - np.exp(-35 * p)) / (1 - np.exp(-35))
    sme = np.where(s < SME_SALES_M,
                   0.04 * (1 - (np.clip(s, 5, 50) - 5) / 45), 0.0)
    corp = 0.12 * w50 + 0.24 * (1 - w50) - np.nan_to_num(sme)
    other = 0.03 * w35 + 0.16 * (1 - w35)
    return np.select([c == "mortgage", c == "qrre",
                      c == "other_retail", c == "corporate"],
                     [0.15, 0.04, other, corp], np.nan)


def maturity_adjustment(pd_, m) -> np.ndarray:
    """Companies' capital rises with maturity; 1 at one year."""
    b = (0.11852 - 0.05478 * np.log(np.asarray(pd_, dtype=float))) ** 2
    return (1 + (np.asarray(m, dtype=float) - 2.5) * b) / (1 - 1.5 * b)


def capital_k(pd_, lgd, cls, m=2.5, sales_m=np.nan,
              confidence=CONFIDENCE) -> np.ndarray:
    """Capital per dollar of EAD for a performing exposure: the loss
    in a 1-in-1,000 year for the shared factor, less expected loss."""
    p = np.asarray(pd_, dtype=float)
    r = correlation(p, cls, sales_m)
    shock = np.sqrt(r) * norm.ppf(confidence)   # a 1-in-1,000 economy
    bad_year = norm.cdf((norm.ppf(p) + shock) / np.sqrt(1 - r))
    k = np.asarray(lgd, dtype=float) * (bad_year - p)
    c = np.broadcast_to(np.asarray(cls, dtype=object), p.shape)
    return k * np.where(c == "corporate", maturity_adjustment(p, m), 1)


def risk_weight(pd_, lgd, cls, m=2.5, sales_m=np.nan,
                scaling=SCALING) -> np.ndarray:
    """IRB risk weight: 12.5 times K (the inverse of 8%)."""
    return 12.5 * scaling * capital_k(pd_, lgd, cls, m, sales_m)


def floor_pd(pd_, cls) -> np.ndarray:
    c = np.asarray(cls, dtype=object)
    lo = np.where(c == "qrre", QRRE_PD_FLOOR, PD_FLOOR)
    return np.maximum(np.asarray(pd_, dtype=float), lo)


# ========================================================= the book

def book(con, as_of=AS_OF) -> pd.DataFrame:
    """Every exposure on `as_of`: each open retail and small-business
    account and each commercial facility, with what both approaches
    need. Drawn and undrawn amounts are in cents."""
    r = _retail(con, as_of)
    c = _commercial(con, as_of)
    b = pd.concat([r, c], ignore_index=True)
    b["cls"] = b["product"].map(CLASS)
    big = (b.segment == "retail") & b["product"].isin(
        ["sme_term", "sme_overdraft"]) & (
        b.drawn_cents + b.undrawn_cents > RETAIL_LIMIT_CENTS)
    b.loc[big, "cls"] = "corporate"           # too big to be retail
    b["guaranteed"] = b["product"].map(GUARANTEED).fillna(0.0)
    for col in ("sales_m", "maturity_years", "collateral_cents"):
        b[col] = pd.to_numeric(b[col], errors="coerce").astype(float)
    return b.sort_values("account_id").reset_index(drop=True)


def _retail(con, as_of) -> pd.DataFrame:
    perf.prepare(con)
    b = con.execute("""
        SELECT c.account_id, c.root_id, c.product,
               c.balance_cents AS drawn_cents,
               coalesce(c.limit_cents, 0) AS limit_cents, c.missed,
               date_diff('month', c.root_open, c.month) AS mob,
               coalesce(a.collateral_value_cents, 0)
                   AS collateral_cents,
               ap.mark1_score, s.turnover_cents
        FROM history c
        JOIN accounts a ON a.account_id = c.account_id
        JOIN accounts r ON r.account_id = c.root_id
        LEFT JOIN applications ap ON ap.app_id = r.app_id
        LEFT JOIN sme_applications s ON s.app_id = r.app_id
        WHERE c.month = ?
          AND c.status IN ('up_to_date', 'arrears', 'default')
        ORDER BY c.account_id""", [as_of]).df()
    loans = pdm.personal_loans(con)[["account_id", "score"]]
    b = b.merge(loans.rename(columns={"account_id": "root_id"}),
                on="root_id", how="left")
    b["score"] = b["score"].where(b["product"] == "personal",
                                  b["mark1_score"])
    b["band"] = "all"
    for p, edges in pdm.SCORE_EDGES.items():
        sel = b["product"] == p
        b.loc[sel, "band"] = pdm.band(b.loc[sel, "score"], edges)
    revolving = b["product"].isin(["card", "sme_overdraft"])
    b["undrawn_cents"] = np.where(
        revolving, (b.limit_cents - b.drawn_cents).clip(lower=0), 0)
    eps = perf.default_episodes(con, pdm.DEFINITION)
    dm, cm = pd.to_datetime(eps.default_month), pd.to_datetime(
        eps.cure_month)
    t = pd.Timestamp(as_of)
    open_ = set(eps.account_id[(dm <= t) & (cm.isna() | (cm > t))])
    b["in_default"] = b.root_id.isin(open_)
    b["segment"] = "retail"
    b["sales_m"] = b.turnover_cents / 1e8
    b["secured"] = b["product"].isin(SECURED) | (
        (b["product"] == "sme_term") & (b.collateral_cents > 0))
    return b.drop(columns=["mark1_score", "turnover_cents"])


def _commercial(con, as_of) -> pd.DataFrame:
    year = pd.Timestamp(as_of).year
    f = con.execute("""
        WITH fm AS (
            SELECT facility_id,
                   max(drawn_cents) FILTER (WHERE status = 'defaulted')
                       AS d_drawn,
                   max(drawn_cents) AS drawn, max(limit_cents) AS lim,
                   bool_or(status = 'defaulted') AS in_default
            FROM facility_months WHERE month = ? GROUP BY 1),
        g AS (SELECT company_id, internal_grade AS grade,
                     row_number() OVER (PARTITION BY company_id
                         ORDER BY rating_date DESC) AS k
              FROM ratings WHERE internal_grade IS NOT NULL
                AND rating_date <= ?),
        ag AS (SELECT company_id, agency_rating AS agency,
                      row_number() OVER (PARTITION BY company_id
                          ORDER BY rating_date DESC) AS k
               FROM ratings WHERE agency_rating IS NOT NULL
                 AND rating_date <= ?),
        fin AS (SELECT company_id, revenue_cents,
                       row_number() OVER (PARTITION BY company_id
                           ORDER BY fiscal_year DESC) AS k
                FROM financials WHERE fiscal_year < ?)
        SELECT f.facility_id AS account_id, f.company_id,
               'commercial_' || f.kind AS product, f.kind, f.secured,
               coalesce(fm.d_drawn, fm.drawn) AS drawn_cents,
               fm.lim AS limit_cents, fm.in_default,
               date_diff('day', ?::DATE, f.maturity_date) / 365.25
                   AS maturity_years,
               g.grade, ag.agency,
               fin.revenue_cents / 1e8 AS sales_m
        FROM facilities f JOIN fm USING (facility_id)
        LEFT JOIN g ON g.company_id = f.company_id AND g.k = 1
        LEFT JOIN ag ON ag.company_id = f.company_id AND ag.k = 1
        LEFT JOIN fin ON fin.company_id = f.company_id AND fin.k = 1
        ORDER BY 1""", [as_of, as_of, as_of, year, as_of]).df()
    # A term loan amortises: its limit is what was lent, not a
    # promise to lend again. Only a revolver's headroom can be drawn.
    f["undrawn_cents"] = np.where(
        f.kind == "revolver", (f.limit_cents - f.drawn_cents).clip(
            lower=0), 0)
    f["unrated"] = f.grade.isna()
    f["grade"] = f.grade.fillna(NEW_CLIENT_GRADE).astype(int)
    f["segment"] = "commercial"
    f["missed"] = 0
    return f.drop(columns=["kind"])


# ================================================= through the cycle

def arrears_pools(con, as_of=AS_OF, min_defaults: int = 20
                  ) -> pd.DataFrame:
    """The long-run share of accounts one or two payments behind at a
    quarter end that defaulted within twelve months, by product and
    payments missed: a pool's through-the-cycle PD. A pool with fewer
    than `min_defaults` defaults takes every product's rate."""
    perf.prepare(con)
    eps = perf.default_episodes(con, pdm.DEFINITION)
    con.register("cap_eps", eps[["account_id", "default_month",
                                 "cure_month"]])
    last = (pd.Timestamp(as_of) - pd.DateOffset(months=12)).date()
    g = con.execute("""
        WITH q AS (
            SELECT h.root_id, h.product, h.month, h.missed
            FROM history h
            WHERE month(h.month) % 3 = 0 AND h.month <= ?
              AND h.status IN ('up_to_date', 'arrears')
              AND h.missed BETWEEN 1 AND 2
              AND NOT EXISTS (
                  SELECT 1 FROM cap_eps e WHERE e.account_id = h.root_id
                    AND e.default_month <= h.month
                    AND (e.cure_month IS NULL
                         OR e.cure_month > h.month)))
        SELECT product, missed, count(*) AS n,
               count(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM cap_eps e
                   WHERE e.account_id = q.root_id
                     AND e.default_month > q.month
                     AND e.default_month
                         <= q.month + INTERVAL 12 MONTH))
                   AS defaults
        FROM q GROUP BY 1, 2 ORDER BY 1, 2""", [last]).df()
    con.unregister("cap_eps")
    allp = g.groupby("missed")[["n", "defaults"]].sum()
    g["rate"] = g.defaults / g.n
    thin = g.defaults < min_defaults
    g.loc[thin, "rate"] = g.loc[thin, "missed"].map(
        allp.defaults / allp.n)
    g["pooled"] = thin
    return g


def ttc_pd(con, b: pd.DataFrame, pools: pd.DataFrame | None = None
           ) -> pd.Series:
    """Each exposure's through-the-cycle 12-month PD, before floors.

    Personal loans: Chapter 18's 12-month model at the decade's
    average unemployment. Other retail accounts up to date: Chapter
    18's hazard model for the product and band, from the account's
    months on the clock, at the same unemployment. Retail accounts
    behind: their arrears pool's long-run rate. Companies: their
    grade on the master scale. In default: 1."""
    lr = pdm.load_json("pd_model.json")["long_run_unemployment"]
    out = pd.Series(np.nan, index=b.index)
    model, hz = pdm.load_pd_model(), pdm.load_hazards()
    pers = b["product"].eq("personal")
    out[pers] = model.pd(b[pers], u_ahead=lr)
    pools = arrears_pools(con) if pools is None else pools
    rate = pools.set_index(["product", "missed"])["rate"]
    rest = b[(b.segment == "retail") & ~pers]
    behind = rest[rest.missed >= 1]
    out[behind.index] = [rate.get((p, min(m, 2))) for p, m
                         in zip(behind["product"], behind.missed)]
    clean = rest[rest.missed < 1]
    free = np.where(clean["product"] == "sme_emergency", 12, 0)
    start = np.maximum(clean.mob.astype(int) - free, 0)
    keys = pd.DataFrame({"product": clean["product"],
                         "band": clean.band, "start": start})
    cache = {k: float(hz[k[0]].term_structure(
                 k[1], np.full(12, lr), start=k[2])
                 .cumulative_pd.iloc[-1])
             for k in set(keys.itertuples(index=False, name=None))}
    out[clean.index] = [cache[k] for k in
                        keys.itertuples(index=False, name=None)]
    com = b.segment.eq("commercial")
    out[com] = b.loc[com, "grade"].map(MASTER_SCALE)
    out[b.in_default.astype(bool)] = 1.0
    return out


# ============================================= risk-weighted assets

def provisions(as_of=AS_OF) -> pd.DataFrame | None:
    """Chapter 20's provision by account, if it has been saved."""
    path = BALLAST / "ecl" / f"ecl_{as_of}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path, columns=["account_id", "stage", "ecl",
                                          "pd12"])


def standardised(b: pd.DataFrame, prov: pd.DataFrame | None = None
                 ) -> pd.DataFrame:
    """Add the standardised exposure, risk weight and RWA (cents)."""
    b = b.copy()
    ccf = b["product"].map(SA_CCF).fillna(0.0)
    b["sa_ccf"] = ccf
    spec = pd.Series(0.0, index=b.index)
    if prov is not None:
        s3 = prov[prov.stage == 3].set_index("account_id")["ecl"]
        spec = b.account_id.map(s3).fillna(0.0)
    b["sa_ead"] = (b.drawn_cents - spec).clip(lower=0) \
        + ccf * b.undrawn_cents
    value = b.collateral_cents.where(b.collateral_cents > 0, 1)
    ltv = np.where(b.collateral_cents > 0, b.drawn_cents / value, np.inf)
    b["ltv"] = np.where(b["product"] == "mortgage", ltv, np.nan)
    rw = np.select(
        [b["product"] == "mortgage", b.cls == "corporate"],
        [sa_mortgage_rw(b.ltv.fillna(0)),
         sa_corporate_rw(b.get("agency", pd.Series(None,
                                                   index=b.index)),
                         b.sales_m)], RETAIL_RW)
    d = b.in_default.astype(bool)
    cover = spec >= COVERED * b.drawn_cents
    rw = np.where(d, np.where(b["product"] == "mortgage",
                              DEFAULTED_MORTGAGE_RW,
                              np.where(cover, DEFAULTED_COVERED_RW,
                                       DEFAULTED_RW)), rw)
    b["sa_rw"] = rw * (1 - b.guaranteed)     # the state's share: 0%
    b["sa_rwa"] = b.sa_ead * b.sa_rw
    return b


def irb_lgd(b: pd.DataFrame, params: dict | None = None,
            mortgage_floor: float = MORTGAGE_LGD_FLOOR,
            corporate_lgd: float = FIRB_LGD) -> pd.DataFrame:
    """Downturn and long-run LGD for each exposure, floors applied.

    Retail: Chapter 19's downturn LGD by product, floored by the
    final Basel standard's floors (and mortgages by the supervisor's
    `mortgage_floor`). The emergency loans' LGD is on the whole loan,
    guarantee included; capital treats the guaranteed share as the
    government's, so the rest carries the loss the guarantee left.
    Companies: the foundation approach's supervisory LGD."""
    p = (params or lgdm.load())["products"]
    dt_ = b["product"].map({k: v["downturn"] for k, v in p.items()})
    lr = b["product"].map({k: v["lgd"] for k, v in p.items()})
    g = b.guaranteed
    dt_, lr = (np.minimum(1, x / (1 - g)) for x in (dt_, lr))
    floor = np.select(
        [b["product"] == "mortgage", b.cls == "qrre", b.secured],
        [max(LGD_FLOOR["mortgage"], mortgage_floor), LGD_FLOOR["qrre"],
         LGD_FLOOR["secured"]], LGD_FLOOR["unsecured"])
    com = b.segment == "commercial"
    out = pd.DataFrame({"lgd": np.where(com, corporate_lgd,
                                        np.maximum(dt_, floor)),
                        "lgd_lr": np.where(com, corporate_lgd,
                                           np.maximum(lr, floor))},
                       index=b.index)
    return out


def irb_ead(b: pd.DataFrame, ccf: dict | None = None,
            revolver_ccf: float = FIRB_CCF) -> np.ndarray:
    """EAD: the balance, plus the expected drawing of any headroom
    (Chapter 19's factors for cards and overdrafts; for companies'
    revolvers, the foundation approach's supervisory factor)."""
    c = (ccf or eadm.load())["ccf"]
    table = pd.DataFrame({"ccf": list(c["card"].values())})
    card = eadm.exposure(b.drawn_cents, b.limit_cents, table)
    od = b.drawn_cents + c["sme_overdraft"] * b.undrawn_cents
    rv = b.drawn_cents + revolver_ccf * b.undrawn_cents
    return np.select([b["product"] == "card",
                      b["product"] == "sme_overdraft",
                      b["product"] == "commercial_revolver"],
                     [card, od, rv], b.drawn_cents).astype(float)


def irb(b: pd.DataFrame, scaling: float = SCALING,
        mortgage_floor: float = MORTGAGE_LGD_FLOOR,
        corporate_lgd: float = FIRB_LGD,
        revolver_ccf: float = FIRB_CCF) -> pd.DataFrame:
    """Add IRB EAD, floored PD, LGD, K, risk weight, RWA and expected
    loss (cents). `b` needs a `pd` column (see `ttc_pd`)."""
    b = b.copy()
    b["irb_ead"] = irb_ead(b, revolver_ccf=revolver_ccf)
    lg = irb_lgd(b, mortgage_floor=mortgage_floor,
                 corporate_lgd=corporate_lgd)
    b["lgd"], b["lgd_lr"] = lg.lgd, lg.lgd_lr
    d = b.in_default.astype(bool).to_numpy()
    p = np.where(d, 0.5, floor_pd(b["pd"], b.cls))  # placeholder if d
    m = np.clip(b.get("maturity_years", pd.Series(2.5, index=b.index))
                .fillna(2.5), *MATURITY)
    k = capital_k(p, b.lgd, b.cls, m, b.sales_m)
    # In default: capital for the gap between the downturn loss and
    # the loss expected now; the expected loss is the long-run LGD.
    k = np.where(d, np.maximum(b.lgd - b.lgd_lr, 0), k)
    b["pd_floored"] = np.where(d, 1.0, p)
    b["m"] = m
    b["k"] = k
    share = 1 - b.guaranteed
    b["irb_rw"] = 12.5 * scaling * k * share
    b["irb_rwa"] = b.irb_ead * b.irb_rw
    b["el"] = b.irb_ead * share * np.where(d, b.lgd_lr,
                                           b.pd_floored * b.lgd)
    return b


# ======================================================= whole bank

def bank_capital(con, as_of=AS_OF) -> dict:
    """Fernhill's capital and its other RWA at a year end (cents)."""
    row = con.execute("""
        SELECT cet1_cents, at1_cents, tier2_cents,
               operational_rwa_cents, market_rwa_cents
        FROM bank_capital WHERE year_end = ?""", [as_of]).fetchone()
    keys = ["cet1", "at1", "tier2", "operational_rwa", "market_rwa"]
    return dict(zip(keys, map(int, row)))


def credit_rwa(r: pd.DataFrame, irb_products=()) -> float:
    """Credit RWA with the named products on IRB, the rest standard."""
    use = r["product"].isin(list(irb_products))
    return float(np.where(use, r.irb_rwa, r.sa_rwa).sum())


def output_floor(rwa: float, sa_rwa: float,
                 floor: float = OUTPUT_FLOOR) -> float:
    """Total RWA may not fall below `floor` times the standardised
    total, computed for the whole bank."""
    return max(rwa, floor * sa_rwa)


def ratios(cap: dict, total_rwa: float, el_gap: float = 0.0,
           credit: float = 0.0, excess_cap: float = EXCESS_CAP) -> dict:
    """CET1, Tier 1 and total capital ratios. `el_gap` is provisions
    less IRB expected loss: a shortfall comes off CET1; an excess is
    added to Tier 2, up to `excess_cap` of credit RWA."""
    cet1 = cap["cet1"] + min(el_gap, 0.0)
    tier1 = cet1 + cap["at1"]
    tier2 = cap["tier2"] + min(max(el_gap, 0.0), excess_cap * credit)
    return {"cet1": cet1 / total_rwa, "tier1": tier1 / total_rwa,
            "total": (tier1 + tier2) / total_rwa}


def requirements(countercyclical: float = COUNTERCYCLICAL) -> dict:
    """Minimums plus the combined buffer, which is held in CET1."""
    buf = CONSERVATION + countercyclical
    return {k: v + buf for k, v in MINIMUM.items()}


def leverage_exposure(b: pd.DataFrame) -> float:
    """The leverage ratio's exposure for the loan book: what is drawn,
    plus undrawn limits at the standardised conversion factors (and
    never less than a tenth of a cancellable limit). No risk weights
    and no credit for the guarantee."""
    ccf = b["product"].map(SA_CCF).fillna(0.10)
    return float((b.drawn_cents + ccf * b.undrawn_cents).sum())


# =========================================================== a run

def run(con, as_of=AS_OF) -> pd.DataFrame:
    """Both approaches for every exposure on `as_of`, one row each."""
    b = book(con, as_of)
    b["pd"] = ttc_pd(con, b)
    r = irb(standardised(b, provisions(as_of)))
    r.attrs["as_of"] = str(as_of)
    return r


def summary(r: pd.DataFrame, by: str = "product") -> pd.DataFrame:
    """EAD, RWA and expected loss by product (dollars), with each
    approach's RWA as a share of its EAD (the RWA density)."""
    g = r.groupby(by)[["drawn_cents", "sa_ead", "sa_rwa", "irb_ead",
                       "irb_rwa", "el"]].sum() / 100
    g.columns = ["drawn", "sa_ead", "sa_rwa", "irb_ead", "irb_rwa",
                 "el"]
    g["sa_density"] = g.sa_rwa / g.sa_ead
    g["irb_density"] = g.irb_rwa / g.irb_ead
    return g


# =========================================================== saving

KEEP = ["account_id", "segment", "product", "cls", "company_id",
        "band", "missed", "mob", "in_default", "secured", "guaranteed",
        "drawn_cents", "limit_cents", "undrawn_cents",
        "collateral_cents", "ltv", "grade", "agency", "sales_m",
        "maturity_years", "sa_ccf", "sa_ead", "sa_rw", "sa_rwa",
        "irb_ead", "pd", "pd_floored", "lgd", "lgd_lr", "m", "k",
        "irb_rw", "irb_rwa", "el"]


def save(r: pd.DataFrame, as_of=AS_OF) -> list[str]:
    """Write RWA by account, with every input `irb` needs to run
    again, and RWA by product, under data/ballast/capital/."""
    OUT.mkdir(parents=True, exist_ok=True)
    acc = OUT / f"rwa_{as_of}.parquet"
    r[KEEP].to_parquet(acc, index=False)
    prod = OUT / f"rwa_by_product_{as_of}.csv"
    summary(r).round(2).to_csv(prod)
    return [str(x.relative_to(ROOT)) for x in (acc, prod)]


def load(as_of=AS_OF) -> pd.DataFrame:
    """RWA by account, as saved for `as_of`."""
    return pd.read_parquet(OUT / f"rwa_{as_of}.parquet")
