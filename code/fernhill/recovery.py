"""What Fernhill got back after an account defaulted and left the book.

Charged-off debt goes to collections, which recover a share over about four years, less
the agency's commission; twice Fernhill sold a block of old charged-off debt to a debt
buyer. Repossessed cars and foreclosed homes are sold, at a discount to what they would
fetch from a willing seller. Emergency business loans carry an 80% government guarantee.
Everything after 31 December 2025 has not happened yet, so a recent default's recovery is
incomplete: the workout is still running.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


END_T = 119                       # December 2025
DEBT_SALES = {41: 0.09, 94: 0.12}  # June 2019 at 9 cents in the dollar; November 2023 at 12
UNSECURED_MEAN = {"personal": 0.21, "card": 0.15, "auto": 0.10, "sme_term": 0.24,
                  "sme_overdraft": 0.16, "sme_emergency": 0.06, "mortgage": 0.05}
AGENCY_COMMISSION = 0.22


def _spread(rng, t0, total, months=48, half_life=8.0):
    """Split a recovery total into monthly payments that tail off."""
    w = 0.5 ** (np.arange(months) / half_life) * rng.uniform(0.5, 1.5, months)
    w = w / w.sum()
    return [(t0 + 1 + k, total * w[k]) for k in range(months)]


def recoveries(closes, defaults, acc, macro: pd.DataFrame, stress: np.ndarray,
               rng: np.random.Generator) -> list[tuple]:
    """Rows of (account index, month index, kind, amount); costs are negative."""
    hpi = macro["house_price_index"].to_numpy()
    cars = macro["used_car_index"].to_numpy()
    first_default = {}
    for i, t, ead, _ in defaults:
        first_default.setdefault(i, (t, ead))
    out = []
    # Directors' personal guarantees on small-business debt: called on, they sometimes pay
    # part. Its own random stream, so the other recoveries are drawn as before.
    g_rng = np.random.default_rng(acc.rng_seed + 2)
    for i, t, reason, bal in closes:
        p = acc.product[i]
        if reason not in ("charged_off", "vehicle_repossessed", "property_sold", "collateral_sold"):
            continue
        z = acc.z[i]
        bal = max(bal, 0.0)
        flows = []
        if p == "sme_emergency" and i in first_default:
            td, ead = first_default[i]
            flows.append((min(td + 6, t + 1), "guarantee", 0.80 * ead))
            bal = max(bal - 0.80 * ead, 0.0)
        if reason == "vehicle_repossessed":
            age_years = (t - acc.open_t[i]) / 12
            value = acc.extra["collateral"][i] * 0.86 ** age_years * cars[min(t, END_T)] / cars[acc.open_t[i]]
            proceeds = min(value * rng.uniform(0.55, 0.85), bal + 1500.0)
            ts = t + int(rng.integers(1, 4))
            flows.append((ts, "collateral_sale", proceeds))
            flows.append((ts, "cost", -1500.0))
            bal = max(bal - proceeds + 1500.0, 0.0)
            mean = 0.08
        elif reason == "property_sold":
            value = acc.extra["collateral"][i] * hpi[min(t, END_T)] / hpi[acc.open_t[i]]
            proceeds = value * rng.uniform(0.80, 0.92)
            costs = 0.06 * proceeds + 3000.0
            # Anything left after the debt and the costs belongs to the borrower.
            proceeds = min(proceeds, bal + costs)
            flows.append((t, "collateral_sale", proceeds))
            flows.append((t, "cost", -costs))
            bal = max(bal - proceeds + costs, 0.0)
            mean = 0.05
        elif reason == "collateral_sold":
            proceeds = min(acc.extra["collateral"][i] * rng.uniform(0.45, 0.80), bal + 2000.0)
            flows.append((t, "collateral_sale", proceeds))
            flows.append((t, "cost", -(0.04 * proceeds + 2000.0)))
            bal = max(bal - proceeds, 0.0)
            mean = 0.10
        else:
            mean = UNSECURED_MEAN[p]
        if p in ("sme_term", "sme_overdraft") and bal > 0 and g_rng.random() < 0.35:
            paid = bal * g_rng.uniform(0.08, 0.35)
            flows.append((t + int(g_rng.integers(4, 13)), "guarantee", paid))
            bal -= paid
        if bal > 0:
            m = np.clip(mean * np.exp(0.35 * z) * (1 - 0.08 * stress[min(t, END_T)]), 0.005, 0.8)
            share = rng.beta(m * 6, (1 - m) * 6)
            tail = _spread(rng, max(t, max((f[0] for f in flows), default=t)), share * bal)
            recovered = 0.0
            for tm, amt in tail:
                if tm in DEBT_SALES and tm - t >= 6 and p in ("personal", "card") and rng.random() < 0.85:
                    remaining = bal - recovered
                    flows.append((tm, "debt_sale", DEBT_SALES[tm] * remaining))
                    break
                flows.append((tm, "collections_payment", amt))
                flows.append((tm, "cost", -AGENCY_COMMISSION * amt))
                recovered += amt
        for tm, kind, amt in flows:
            if tm <= END_T and abs(amt) >= 0.005:
                out.append((i, tm, kind, amt))
    return out
