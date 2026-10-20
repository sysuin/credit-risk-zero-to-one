"""Fernhill's commercial book: mid-sized companies, their accounts, their facilities,
their ratings, and, for the listed ones, what the stock market thought of them.

Each company is a firm-value model underneath. Its assets follow a random walk with a
drift, driven partly by one economy-wide factor and partly by its own luck; it defaults
when their value falls below its default point (short-term debt plus half its long-term
debt). Its accounts, its share price and its spreads are all read off that value, so the
Merton model of Chapter 17 is the right model of this world, and the internal ratings that
analysts assign once a year are a slower, stickier view of the same thing.

Meridian Supply Co., the company of the earlier books, is among them, as a prospect: its
revenue and cost of goods for 2022 to 2025 are those of the earlier books' warehouse.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

SECTORS = ["manufacturing", "wholesale", "retail", "construction", "real_estate",
           "technology", "healthcare", "energy", "transport", "business_services"]
SECTOR_VOL = np.array([0.24, 0.20, 0.26, 0.30, 0.22, 0.38, 0.20, 0.34, 0.27, 0.23])
SECTOR_BETA = np.array([1.0, 0.9, 1.2, 1.3, 1.1, 0.8, 0.5, 1.0, 1.2, 0.9])
MASTER_SCALE = np.array([0.0003, 0.0007, 0.0015, 0.003, 0.006, 0.012, 0.024, 0.05, 0.10, 0.20])
AGENCY = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]
# An agency's letter, read off a year's average distance to default (higher is safer).
AGENCY_DD_EDGES = np.array([9.5, 8.0, 6.5, 4.8, 3.3, 2.0])

# From Book 2's warehouse (v_sales), summed by calendar year: revenue and cost of goods.
MERIDIAN_REVENUE = {2022: 61_262_036, 2023: 101_423_619, 2024: 111_984_543, 2025: 127_348_346}
MERIDIAN_COGS = {2022: 43_257_200, 2023: 71_013_580, 2024: 76_958_401, 2025: 88_187_302}

N_START = 230
# Companies' accounting habits come from their own stream, so the firm-value paths do not move.
SEED_ACCOUNTS = 2029
NAMES_A = ["Ash", "Birch", "Cedar", "Delta", "Elm", "Falcon", "Granite", "Harbour", "Iron", "Juniper",
           "Kestrel", "Linden", "Maple", "North", "Oak", "Pine", "Quarry", "River", "Stone", "Thorn",
           "Upland", "Vale", "Willow", "Yew", "Alder", "Beacon", "Copper", "Dale", "Ember", "Flint"]
NAMES_B = ["Industries", "Holdings", "Group", "Logistics", "Foods", "Engineering", "Systems",
           "Healthcare", "Energy", "Homes", "Retail", "Components", "Partners", "Freight", "Materials"]


def _names(n, rng):
    seen, out = set(), []
    while len(out) < n:
        nm = f"{rng.choice(NAMES_A)} {rng.choice(NAMES_A)} {rng.choice(NAMES_B)}"
        a, b = nm.split()[:2]
        if a != b and nm not in seen:
            seen.add(nm)
            out.append(nm)
    return out


def bs_equity(V, D, r, sigma, T=1.0):
    d1 = (np.log(V / D) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    E = V * norm.cdf(d1) - D * np.exp(-r * T) * norm.cdf(d2)
    return E, d1, d2


def simulate(macro: pd.DataFrame, stress: np.ndarray, rng: np.random.Generator) -> dict:
    T = len(macro)
    months = pd.to_datetime(macro["month"]).dt.date.to_numpy()
    policy = macro["policy_rate_pct"].to_numpy() / 100
    # The economy-wide factor: monthly shocks, with the 2020 crash and the 2022 rate shock in them.
    ds = np.diff(np.concatenate([[stress[0]], stress]))
    systematic = 0.6 * rng.normal(0, 1, T) - 2.6 * ds - 0.08
    fin_rng = np.random.default_rng(SEED_ACCOUNTS)

    companies, fin_rows, fac_rows, fac_month, ratings, market, defaults, recov, truth = [], [], [], [], [], [], [], [], []
    cid = 0

    def new_company(t0, *, name=None, sector=None, listed=None, quality=None):
        nonlocal cid
        cid += 1
        s = rng.integers(0, len(SECTORS)) if sector is None else sector
        q = rng.normal(0, 1) if quality is None else quality
        debt = float(np.exp(rng.normal(17.6, 0.8)))                      # about $44m, widely spread
        st_share = rng.uniform(0.2, 0.5)
        asset_ratio = np.clip(2.1 + 0.5 * q + rng.normal(0, 0.15), 1.4, 5.0)
        sigma = SECTOR_VOL[s] * rng.uniform(0.8, 1.2)
        return dict(company_id=f"C{cid:04d}", name=name, sector=SECTORS[s], sector_idx=s,
                    listed=bool(rng.random() < 0.28) if listed is None else listed,
                    debt=debt, st_share=st_share, V=debt * asset_ratio, sigma=sigma,
                    beta=SECTOR_BETA[s], mu=0.035 + 0.01 * q + 0.5 * sigma ** 2, margin=rng.uniform(0.07, 0.16),
                    turnover=rng.uniform(0.6, 1.8), start_t=t0, alive=True, grade=None,
                    q=q, facilities=[], last_V=None)

    pool = []
    names = iter(_names(400, rng))
    for _ in range(N_START):
        c = new_company(0)
        c["name"] = next(names)
        pool.append(c)

    def open_facility(c, kind, t, fid):
        limit = float(np.round(c["debt"] * rng.uniform(0.15, 0.45), -3))
        tenor = int(rng.choice([36, 60, 84]))
        secured = bool(rng.random() < (0.75 if kind == "term" else 0.45))
        c["facilities"].append(dict(facility_id=fid, kind=kind, limit=limit, start_t=t,
                                    maturity_t=t + tenor, secured=secured,
                                    util_base=rng.uniform(0.2, 0.5), drawn=0.0, renewals=0))
        # The same three draws as always (so nothing after them moves), now used as the
        # noise around terms set from the borrower: covenants with headroom over its
        # leverage and interest cover at signing, and a margin that rises with its risk.
        m_draw = int(rng.choice([175, 225, 275, 325, 400]))
        lev_draw = float(rng.choice([3.0, 3.5, 4.0, 4.5]))
        cov_draw = float(rng.choice([2.5, 3.0, 3.5, 4.0]))
        DP = c["debt"] * (c["st_share"] + 0.5 * (1 - c["st_share"]))
        health = np.tanh(np.log(c["V"] / DP))
        ebitda = max(c["V"] * c["turnover"] * c["margin"] * (0.55 + 0.45 * health), 1.0)
        lev = c["debt"] / ebitda
        icr = ebitda / max(c["debt"] * (policy[t] + 0.0275), 1.0)
        if "last_lev" in c:                 # a client Fernhill already holds accounts for
            lev, icr = c["last_lev"], c["last_icr"]
        dd = np.log(c["V"] / DP) / c["sigma"]
        max_lev = float(np.clip(np.round((lev * 1.35 + 0.6 + 0.25 * (lev_draw - 3.75)) * 4) / 4, 2.0, 6.5))
        min_icr = float(np.clip(np.round((icr * 0.7 + 0.25 * (cov_draw - 3.25)) * 4) / 4, 1.25, 6.0))
        margin = int(np.clip(np.round((175 + 60 * (5 - dd) - (40 if secured else 0) + 0.3 * (m_draw - 275)) / 25)
                             * 25, 125, 650))
        fac_rows.append((fid, c["company_id"], kind, months[t], months[min(t + tenor, T - 1)] if t + tenor < T else
                         (pd.Timestamp(months[0]) + pd.DateOffset(months=t + tenor)).date(),
                         round(limit * 100), margin, secured, "senior", max_lev, min_icr))
        return c["facilities"][-1]

    def add_facilities(c, t):
        n_fac = rng.choice([1, 2, 3], p=[0.45, 0.4, 0.15])
        kinds = ["revolver", "term"] if n_fac >= 2 else [rng.choice(["revolver", "term"])]
        if n_fac == 3:
            kinds.append("term")
        for k, kind in enumerate(kinds):
            open_facility(c, kind, t, f"{c['company_id']}-F{k + 1}")

    for c in pool:
        add_facilities(c, int(rng.integers(0, 24)) if rng.random() < 0.3 else 0)

    for t in range(T):
        r = policy[t]
        for c in pool:
            if not c["alive"] or c["start_t"] > t:
                continue
            dt = 1 / 12
            eps = c["beta"] / 1.2 * 0.55 * systematic[t] + np.sqrt(1 - 0.55 ** 2) * rng.normal()
            c["V"] *= np.exp((c["mu"] - 0.5 * c["sigma"] ** 2) * dt + c["sigma"] * np.sqrt(dt) * eps)
            c["debt"] *= np.exp(0.002 + rng.normal(0, 0.004))
            DP = c["debt"] * (c["st_share"] + 0.5 * (1 - c["st_share"]))
            dd = (np.log(c["V"] / DP) + (c["mu"] - 0.5 * c["sigma"] ** 2)) / c["sigma"]
            pd1 = float(norm.cdf(-dd))
            truth.append((c["company_id"], months[t], pd1, float(dd)))
            # A facility that matured last month is renewed, on terms set afresh, for a
            # client still in business: most commercial lending rolls over.
            for f in list(c["facilities"]):
                if f["maturity_t"] == t - 1:
                    base = f["facility_id"].split("R")[0]
                    nf = open_facility(c, f["kind"], t, f"{base}R{f['renewals'] + 1}")
                    nf["renewals"] = f["renewals"] + 1
            for f in c["facilities"]:
                if f["start_t"] > t or f["maturity_t"] < t:
                    continue
                if f["kind"] == "revolver":
                    u = np.clip(f["util_base"] + 0.5 * norm.cdf(-dd + 1.5) + rng.normal(0, 0.04), 0, 1.0)
                    f["drawn"] = u * f["limit"]
                else:
                    age = t - f["start_t"]
                    tenor = f["maturity_t"] - f["start_t"]
                    f["drawn"] = f["limit"] * max(1 - 0.6 * age / tenor, 0.0)
                fac_month.append((f["facility_id"], months[t], round(f["drawn"] * 100), round(f["limit"] * 100), "performing"))
            if c["listed"]:
                E, d1, _ = bs_equity(c["V"], DP, r + 0.005, c["sigma"])
                evol = c["sigma"] * c["V"] / max(E, 1) * norm.cdf(d1)
                q_pd = float(norm.cdf(-(np.log(c["V"] / DP) + (r - 0.5 * c["sigma"] ** 2)) / c["sigma"]))
                cds = None
                if c["debt"] > 6e7:
                    cds = round(max(-np.log(1 - min(q_pd * 1.6, 0.95)) * 0.6 * 10000, 15) + rng.normal(0, 4), 1)
                market.append((c["company_id"], months[t], round(max(E, 0) * 100), round(float(min(evol, 3.0)), 4), cds))
            # Default
            if c["V"] < DP:
                c["alive"] = False
                kind = rng.choice(["payment", "bankruptcy", "distressed_restructuring"], p=[0.45, 0.30, 0.25])
                defaults.append((c["company_id"], months[t], kind))
                for f in c["facilities"]:
                    if f["start_t"] <= t <= f["maturity_t"]:
                        ead = f["drawn"] if f["kind"] == "term" else max(f["drawn"], f["limit"] * min(1.0, f["util_base"] + 0.55))
                        rate = rng.beta(6, 4) if f["secured"] else rng.beta(3, 5)
                        lag = int(rng.integers(9, 30))
                        if t + lag <= T - 1:
                            recov.append((f["facility_id"], months[t + lag], "restructuring" if kind != "bankruptcy" else "liquidation",
                                          round(ead * rate * 100)))
                            recov.append((f["facility_id"], months[t + lag], "cost", -round(ead * 0.03 * 100)))
                        fac_month.append((f["facility_id"], months[t], round(ead * 100), round(f["limit"] * 100), "defaulted"))
                # A new client replaces it within a few months.
                if t + 3 < T:
                    nc = new_company(t + 3)
                    nc["name"] = next(names)
                    pool.append(nc)
                    add_facilities(nc, t + 3)
        # Annual accounts and rating review each April for the year just ended.
        if months[t].month == 3 and t >= 12:
            fy = months[t].year - 1
            for c in pool:
                if not c["alive"] or c["start_t"] > t - 3:
                    continue
                fin_rows.append(_accounts(c, fy, policy[t], rng, fin_rng))
                grade = _review(c, fin_rows[-1], rng)
                ratings.append((c["company_id"], months[t], grade, c["model_grade"], bool(c["override"]), None))
        # Agency ratings move each quarter for the larger listed companies, on a smoothed view.
        if months[t].month in (3, 6, 9, 12):
            for c in pool:
                if c["alive"] and c["listed"] and c["debt"] > 5e7 and c["start_t"] <= t:
                    recent = [x[3] for x in truth[-4000:] if x[0] == c["company_id"]][-12:]
                    smooth = float(np.mean(recent))
                    letter = AGENCY[int(np.sum(smooth < AGENCY_DD_EDGES))]
                    ratings.append((c["company_id"], months[t], None, None, None, letter))

    for c in pool:
        companies.append((c["company_id"], c["name"], c["sector"], bool(c["listed"]), months[c["start_t"]]))

    # Meridian, the prospect.
    meridian_id = f"C{cid + 1:04d}"
    companies.append((meridian_id, "Meridian Supply Co.", "wholesale", False, None))
    fin_rows.extend(_meridian_accounts(meridian_id))
    return dict(companies=companies, financials=fin_rows, facilities=fac_rows, facility_month=fac_month,
                ratings=ratings, market=market, defaults=defaults, recoveries=recov, truth=truth,
                meridian_id=meridian_id)


def _u(x, lo, hi, spread=0.08):
    """Turn a uniform draw on [lo, hi] into a multiplier around 1."""
    return 1 + spread * (2 * (x - lo) / (hi - lo) - 1)


def _accounts(c, fy, r, rng, fin_rng):
    """One year's accounts. The firm's value sets its sales, margins and debt; its habits
    (how long its customers take to pay, how much stock it holds, how much of its profit
    its owners take out) are its own and change little from year to year; and the three
    statements articulate: equity moves by profit less dividends, fixed assets by
    investment less depreciation, and cash is what is left."""
    if "profile" not in c:
        c["profile"] = dict(recv_days=fin_rng.uniform(35, 75), inv_days=fin_rng.uniform(20, 70),
                            pay_days=fin_rng.uniform(30, 60), cash_ratio=fin_rng.uniform(0.02, 0.08),
                            cogs_share=fin_rng.uniform(0.6, 0.8), dep_share=fin_rng.uniform(0.02, 0.05),
                            capex_mult=fin_rng.uniform(0.9, 1.4), payout=fin_rng.uniform(0.0, 0.5))
    pf = c["profile"]
    # Twelve draws from the main stream, in the order they have always been drawn, so the
    # firm-value paths and defaults that follow are unchanged; here they are the year's noise.
    d = [rng.lognormal(0, 0.05), rng.normal(0, 0.01), rng.uniform(0.02, 0.05), rng.uniform(0.02, 0.035),
         rng.uniform(0.02, 0.10), rng.uniform(0.10, 0.20), rng.uniform(0.05, 0.18), rng.uniform(0.06, 0.12),
         rng.uniform(0.8, 1.4), rng.normal(0.02, 0.02), rng.uniform(0.1, 0.2), rng.uniform(0.6, 0.8)]
    V = c["V"]
    revenue = V * c["turnover"] * d[0]
    DP = c["debt"] * (c["st_share"] + 0.5 * (1 - c["st_share"]))
    health = np.tanh(np.log(V / DP))
    margin = max(c["margin"] * (0.55 + 0.45 * health) + d[1], -0.08)
    ebitda = revenue * margin
    cogs = (revenue - ebitda) * pf["cogs_share"] * _u(d[11], 0.6, 0.8, 0.03)
    opex = revenue - cogs - ebitda
    dep = revenue * pf["dep_share"] * _u(d[2], 0.02, 0.05, 0.05)
    debt = c["debt"]
    interest = debt * (r + d[3])
    ebit = ebitda - dep
    tax = max(ebit - interest, 0) * 0.25
    net = ebit - interest - tax
    receivables = revenue * pf["recv_days"] * _u(d[5], 0.10, 0.20) / 365
    inventory = cogs * pf["inv_days"] * _u(d[6], 0.05, 0.18) / 365
    payables = cogs * pf["pay_days"] * _u(d[7], 0.06, 0.12) / 365
    accruals = revenue * 0.03
    capex = dep * pf["capex_mult"] * _u(d[8], 0.8, 1.4, 0.15)
    wc = receivables + inventory - payables
    if "equity" not in c:
        fixed = max(0.85 * V - receivables - inventory, 0.1 * revenue)
        cash = revenue * pf["cash_ratio"] * _u(d[4], 0.02, 0.10, 0.2)
        equity = cash + receivables + inventory + fixed - payables - accruals - debt
        dividends = 0.0
        ocf = net + dep - wc * 0.05          # the first year seen: little change in working capital
    else:
        fixed = c["fixed"] + capex - dep
        dividends = pf["payout"] * max(net, 0)
        floor = 0.01 * revenue
        cash = c["equity"] + net - dividends + payables + accruals + debt - receivables - inventory - fixed
        if cash < floor:                   # owners leave the money in when it is short
            back = min(dividends, floor - cash)
            dividends -= back
            cash += back
        if cash < floor:                   # and the shortfall is borrowed short term
            debt += floor - cash
            cash = floor
        ceiling = 3 * pf["cash_ratio"] * revenue
        if cash > ceiling:                 # and cash beyond what the business needs is paid out
            dividends += cash - ceiling
            cash = ceiling
        equity = c["equity"] + net - dividends
        ocf = net + dep - (wc - c["wc"]) + (accruals - c["accruals"])
    c.update(equity=equity, fixed=fixed, wc=wc, accruals=accruals,
             last_lev=debt / max(ebitda, 1.0) if ebitda > 0 else 8.0,
             last_icr=max(ebitda, 0.0) / max(interest, 1.0))
    total_assets = cash + receivables + inventory + fixed
    current_assets = cash + receivables + inventory
    current_liabilities = payables + accruals + debt * c["st_share"]
    vals = [revenue, cogs, opex, ebitda, dep, ebit, interest, tax, net, cash, receivables, inventory,
            current_assets, total_assets, current_liabilities, debt, equity, capex, ocf, payables, dividends]
    return (c["company_id"], fy, *[int(round(v * 100)) for v in vals], "audited")


def _review(c, row, rng):
    """The annual credit review: a rating model on the accounts, then the analyst."""
    revenue, ebitda, interest, debt = row[2] / 100, row[5] / 100, row[8] / 100, row[17] / 100
    lev = debt / max(ebitda, 1)
    icr = ebitda / max(interest, 1)
    size = np.log10(max(revenue, 1))
    score = 1.2 * np.log(max(lev, 0.1)) - 0.9 * np.log(max(icr, 0.2)) - 0.5 * (size - 8) + rng.normal(0, 0.25)
    model_grade = int(np.clip(np.round(5.5 + 1.6 * score), 1, 10))
    old = c["grade"]
    override = False
    if old is None:
        grade = model_grade
    else:
        move = model_grade - old
        # Analysts move a rating one notch at a time unless the model moves three or more.
        grade = old + int(np.sign(move)) if 0 < abs(move) < 3 else model_grade
        hold = rng.random() < 0.25          # drawn every time, so the stream never depends on the grade
        if abs(move) >= 1 and hold:
            grade, override = old, True
    c["grade"], c["model_grade"], c["override"] = int(grade), model_grade, override
    return int(grade)


def _meridian_accounts(cid):
    """Meridian's four years, articulated from a 2021 balance sheet. Revenue and cost of
    goods are Book 2's; the rest is Meridian's finance director's, as given to Fernhill."""
    rev = {**MERIDIAN_REVENUE, 2021: 52_000_000}
    cogs = {**MERIDIAN_COGS, 2021: 36_800_000}
    opex = {2022: 13_950_000, 2023: 20_910_000, 2024: 23_420_000, 2025: 27_610_000}
    dep = {2022: 1_120_000, 2023: 1_480_000, 2024: 1_760_000, 2025: 1_990_000}
    debt = {2021: 8_000_000, 2022: 9_000_000, 2023: 11_000_000, 2024: 12_500_000, 2025: 14_800_000}
    rate = {2022: 0.052, 2023: 0.078, 2024: 0.081, 2025: 0.077}
    receivable_days = {2021: 46, 2022: 48, 2023: 52, 2024: 58, 2025: 66}
    inventory_days = {2021: 50, 2022: 52, 2023: 54, 2024: 55, 2025: 55}
    payable_days = {2021: 46, 2022: 46, 2023: 45, 2024: 44, 2025: 43}
    dividends = {2022: 300_000, 2023: 500_000, 2024: 2_000_000, 2025: 3_600_000}
    accruals = 1_200_000

    def wc_parts(y):
        return (round(rev[y] * receivable_days[y] / 365), round(cogs[y] * inventory_days[y] / 365),
                round(cogs[y] * payable_days[y] / 365))

    recv, inv, pay = wc_parts(2021)
    fixed, cash = 8_600_000, 3_000_000
    equity = cash + recv + inv + fixed - pay - accruals - debt[2021]
    rows = []
    for fy in (2022, 2023, 2024, 2025):
        ebitda = rev[fy] - cogs[fy] - opex[fy]
        ebit = ebitda - dep[fy]
        interest = round(debt[fy] * rate[fy])
        tax = round(max(ebit - interest, 0) * 0.25)
        net = ebit - interest - tax
        capex = round(dep[fy] * 1.35)
        prev_wc = recv + inv - pay
        recv, inv, pay = wc_parts(fy)
        fixed = fixed + capex - dep[fy]
        equity = equity + net - dividends[fy]
        cash = equity + pay + accruals + debt[fy] - recv - inv - fixed
        ocf = net + dep[fy] - ((recv + inv - pay) - prev_wc)
        ca = cash + recv + inv
        ta = ca + fixed
        cl = pay + accruals + round(debt[fy] * 0.35)
        vals = [rev[fy], cogs[fy], opex[fy], ebitda, dep[fy], ebit, interest, tax, net, cash, recv, inv, ca, ta,
                cl, debt[fy], equity, capex, ocf, pay, dividends[fy]]
        rows.append((cid, fy, *[int(v * 100) for v in vals], "management" if fy == 2025 else "audited"))
    return rows
