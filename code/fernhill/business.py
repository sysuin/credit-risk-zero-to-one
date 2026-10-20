"""Small businesses: who applies, what Fernhill sees, and what it decided.

Fernhill's small-business book is term loans and overdrafts to firms with up to about
$10m of turnover, plus the government-guaranteed emergency loans of 2020-21, made in a
hurry on light checks with an 80% guarantee and a year before the first payment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fernhill.applicants import REGION_SHARE, REGIONS, annuity, sigmoid

SECTORS = ["retail", "hospitality", "construction", "manufacturing", "wholesale",
           "professional_services", "transport", "health"]
SECTOR_SHARE = np.array([0.17, 0.12, 0.15, 0.10, 0.10, 0.18, 0.09, 0.09])
SECTOR_MACRO = np.array([1.20, 1.45, 1.30, 1.00, 1.00, 0.70, 1.10, 0.60])
SECTOR_SHOCK_2020 = np.array([0.9, 1.7, 0.5, 0.3, 0.3, 0.1, 0.8, 0.0])
SECTOR_RISK = np.array([0.05, 0.25, 0.20, 0.0, 0.0, -0.20, 0.10, -0.25])


def make_businesses(n: int, rng: np.random.Generator) -> pd.DataFrame:
    sector = rng.choice(len(SECTORS), n, p=SECTOR_SHARE)
    z = rng.normal(0, 1, n) - SECTOR_RISK[sector]
    years = np.clip(np.round(rng.gamma(2.0, 4.5, n) + 0.8 * z), 0, 60).astype(int)
    form = rng.choice(["sole_trader", "partnership", "limited"], n, p=[0.30, 0.12, 0.58])
    turnover = np.round(np.exp(12.6 + 0.35 * z + 0.04 * np.minimum(years, 20) + rng.normal(0, 0.9, n)
                               + 0.6 * (form == "limited")), -3)
    turnover = np.clip(turnover, 40000, 12_000_000)
    region = rng.choice(len(REGIONS), n, p=REGION_SHARE)
    ids = np.array([f"B{i:05d}" for i in range(1, n + 1)])
    return pd.DataFrame({"business_id": ids, "sector_idx": sector, "sector": np.array(SECTORS)[sector],
                         "legal_form": form, "years_trading_2016": years, "turnover_2016": turnover,
                         "region": np.array(REGIONS)[region], "z": z})


def make_applications(biz: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n_biz = len(biz)
    for year in range(2016, 2026):
        for month in range(1, 13):
            k = rng.poisson(95 + 6 * (year - 2016) if not (year == 2020 and 4 <= month <= 8) else 40)
            prod = rng.choice(["sme_term", "sme_overdraft"], k, p=[0.68, 0.32])
            for p in prod:
                rows.append((year, month, int(rng.integers(0, n_biz)), p))
            if (year == 2020 and month >= 5) or (year == 2021 and month <= 3):
                k2 = rng.poisson(310 if year == 2020 and month <= 7 else 160)
                for _ in range(k2):
                    rows.append((year, month, int(rng.integers(0, n_biz)), "sme_emergency"))
    df = pd.DataFrame(rows, columns=["year", "month", "biz_idx", "product"])
    days = pd.to_datetime(dict(year=df.year, month=df.month, day=1)).dt.days_in_month
    df["app_date"] = pd.to_datetime(dict(year=df.year, month=df.month,
                                         day=(rng.random(len(df)) * days).astype(int) + 1)).dt.date
    b = biz.iloc[df["biz_idx"].to_numpy()].reset_index(drop=True)
    yrs = (df["year"].to_numpy() - 2016)
    z = b["z"].to_numpy() + rng.normal(0, 0.35, len(df))     # firms change; so do their prospects
    turnover = np.round(b["turnover_2016"].to_numpy() * np.exp(0.03 * yrs + rng.normal(0, 0.15, len(df))), -3)
    years_trading = b["years_trading_2016"].to_numpy() + yrs
    owner_age = np.clip(np.round(rng.normal(47, 10, len(df))), 21, 80).astype(int)
    raw = 0.85 * z + rng.normal(0, 0.5, len(df))
    d = pd.DatetimeIndex(pd.to_datetime(df["app_date"]))
    v3 = d >= pd.Timestamp("2019-07-01")
    owner_score = np.where(v3, np.clip(np.round(645 + 80 * raw), 300, 850), np.clip(np.round(610 + 72 * raw), 300, 850))
    business_score = np.clip(np.round(50 + 17 * (0.8 * z + rng.normal(0, 0.6, len(df)))), 1, 100)
    ob = np.ones(len(df), dtype=bool) & (d >= pd.Timestamp("2019-01-01")) & (rng.random(len(df)) < 0.7)
    avg_bal = np.where(ob, np.round(turnover / 12 * np.exp(-1.6 + 0.4 * z + rng.normal(0, 0.5, len(df)))), np.nan)
    credits = np.where(ob, np.round(turnover / 12 * rng.lognormal(0, 0.1, len(df))), np.nan)
    vol = np.where(ob, np.round(np.clip(rng.gamma(2, 0.1, len(df)) * np.exp(-0.25 * z), 0.02, 2), 3), np.nan)
    od_days = np.where(ob, np.clip(np.round(rng.exponential(np.exp(2.0 - 0.8 * z))), 0, 90), np.nan)
    returned = np.where(ob, rng.poisson(np.exp(-1.3 - 0.9 * z)), np.nan)
    existing_debt = np.round(turnover * np.clip(rng.gamma(1.5, 0.08, len(df)) - 0.02 * z, 0, 0.8), -3)
    prod = df["product"].to_numpy()
    amt = np.where(prod == "sme_emergency", np.minimum(np.round(turnover * 0.25, -3), 250000),
                   np.round(np.clip(turnover * np.exp(-2.0 + rng.normal(0, 0.6, len(df))), 5000, 1_500_000), -3))
    term = np.where(prod == "sme_term", rng.choice([24, 36, 48, 60, 84], len(df), p=[0.15, 0.3, 0.2, 0.25, 0.1]),
                    np.where(prod == "sme_emergency", 72, 0))
    secured = (prod == "sme_term") & (amt > 150000) & (rng.random(len(df)) < 0.7)
    collateral = np.where(secured, np.round(amt * rng.uniform(1.0, 2.0, len(df)), -3), np.nan)
    return pd.DataFrame({
        "business_id": b["business_id"], "app_date": df["app_date"], "product": prod,
        "sector": b["sector"], "sector_idx": b["sector_idx"], "region": b["region"], "legal_form": b["legal_form"],
        "years_trading": years_trading, "turnover": turnover, "owner_age": owner_age,
        "owner_bureau_score": owner_score, "business_score": business_score,
        "ob_avg_balance": avg_bal, "ob_monthly_credits": credits, "ob_volatility": vol,
        "ob_overdraft_days": od_days, "ob_returned_items": returned,
        "existing_debt": existing_debt, "amount_requested": amt, "term_requested": term,
        "secured": secured, "collateral_value": collateral,
        "z": z,
    }).sort_values("app_date", kind="stable").reset_index(drop=True)


def decide(a: pd.DataFrame, policy_rate: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """SME-1, Fernhill's expert scorecard for small business, and its policy."""
    n = len(a)
    prod = a["product"].to_numpy()
    pts = np.clip((a["owner_bureau_score"].to_numpy() - 450) / 4, 0, 100)
    pts += a["business_score"].to_numpy() * 0.9
    pts += np.select([a["years_trading"].to_numpy() < 2, a["years_trading"].to_numpy() < 5], [0, 20], 35)
    lev = (a["existing_debt"].to_numpy() + a["amount_requested"].to_numpy()) / np.maximum(a["turnover"].to_numpy(), 1)
    pts += np.select([lev < 0.15, lev < 0.3, lev < 0.5], [40, 28, 12], 0)
    pts += np.where(a["secured"].to_numpy(), 20, 0)
    pts = np.round(pts).astype(int)
    d = pd.DatetimeIndex(pd.to_datetime(a["app_date"]))
    cut = np.where(d >= pd.Timestamp("2020-04-01"), 150, 140)
    cut = np.where(d >= pd.Timestamp("2021-07-01"), 145, cut)
    approve = (pts >= cut) & (lev < 0.8)
    # Emergency loans: the scheme said lend unless the firm was already failing.
    approve = np.where(prod == "sme_emergency", (a["business_score"].to_numpy() > 12) & (rng.random(n) < 0.97), approve)
    reason = np.where(approve, None, np.where(lev >= 0.8, "leverage", "score_below_cutoff"))
    margin = np.select([pts >= 200, pts >= 175, pts >= 155], [3.25, 4.25, 5.5], 6.75)
    rate = np.where(prod == "sme_emergency", 2.5, policy_rate + margin)
    limit_or_amount = np.where(approve, a["amount_requested"].to_numpy(), np.nan)
    return pd.DataFrame({"sme1_score": pts, "cutoff": cut, "decision": np.where(approve, "approve", "decline"),
                         "decline_reason": reason, "offered_rate": np.where(approve, np.round(rate, 2), np.nan),
                         "offered_amount": limit_or_amount, "margin": margin})


def take_up(a: pd.DataFrame, dec: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    p = np.where(a["product"].to_numpy() == "sme_emergency", 0.96, sigmoid(1.6 - 0.25 * dec["margin"].to_numpy() + 0.0 * a["z"].to_numpy()))
    return (dec["decision"].to_numpy() == "approve") & (rng.random(len(a)) < p)


def monthly_payment(amount, rate, term):
    return annuity(amount, rate, term)
