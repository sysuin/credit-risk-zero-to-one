"""The economy Fernhill lends into: ten years of monthly history and the scenarios that
look forward from 31 December 2025.

The history is drawn from anchor points with a little seeded noise. It is shaped like the
decade most lenders lived through: a long, calm expansion; a sharp shock in spring 2020
with payment holidays and government-guaranteed loans; a used-car and house-price boom;
inflation and the fastest rise in interest rates in a generation; a slow drift up in
unemployment while rates stayed high.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd


def month_ends(first: str, last: str) -> pd.DatetimeIndex:
    return pd.date_range(first, last, freq="ME")


HISTORY = month_ends("2016-01-31", "2025-12-31")
FORWARD = month_ends("2026-01-31", "2030-12-31")

# (month, value) anchors; values between anchors are interpolated linearly.
UNEMPLOYMENT = [
    ("2016-01", 5.4), ("2017-01", 4.9), ("2018-01", 4.4), ("2019-01", 4.0),
    ("2020-02", 3.9), ("2020-04", 9.6), ("2020-07", 8.2), ("2020-12", 6.9),
    ("2021-06", 5.8), ("2021-12", 4.6), ("2022-06", 4.0), ("2022-12", 4.1),
    ("2023-06", 4.5), ("2023-12", 5.0), ("2024-06", 5.4), ("2024-12", 5.3),
    ("2025-06", 5.1), ("2025-12", 5.0),
]
# Policy rate changes: the rate set in that month and held until the next change.
POLICY_RATE = [
    ("2016-01", 0.50), ("2017-06", 1.00), ("2018-06", 1.50), ("2019-01", 1.75),
    ("2020-03", 0.25), ("2022-03", 0.50), ("2022-06", 1.50), ("2022-09", 2.75),
    ("2022-12", 3.75), ("2023-03", 4.25), ("2023-07", 4.75), ("2024-09", 4.50),
    ("2024-12", 4.25), ("2025-06", 4.00), ("2025-12", 3.75),
]
GDP_GROWTH = [
    ("2016-01", 2.1), ("2019-12", 2.3), ("2020-03", 0.4), ("2020-06", -9.1),
    ("2020-12", -2.4), ("2021-06", 8.0), ("2021-12", 5.1), ("2022-12", 2.6),
    ("2023-06", 0.6), ("2023-12", 0.4), ("2024-12", 1.0), ("2025-12", 1.6),
]
HOUSE_PRICES = [
    ("2016-01", 100.0), ("2020-02", 121.6), ("2020-06", 119.0), ("2022-06", 146.3),
    ("2023-12", 133.1), ("2025-12", 137.4),
]
USED_CARS = [
    ("2016-01", 100.0), ("2021-01", 105.1), ("2022-06", 142.0), ("2024-06", 115.2),
    ("2025-12", 112.3),
]
INFLATION = [
    ("2016-01", 1.6), ("2020-12", 1.2), ("2021-06", 3.4), ("2022-09", 7.6),
    ("2023-12", 3.1), ("2024-12", 2.6), ("2025-12", 2.4),
]


def _interpolate(anchors, index: pd.DatetimeIndex) -> np.ndarray:
    xs = np.array([pd.Period(m, "M").ordinal for m, _ in anchors], dtype=float)
    ys = np.array([v for _, v in anchors], dtype=float)
    t = np.array([p.ordinal for p in index.to_period("M")], dtype=float)
    return np.interp(t, xs, ys)


def _steps(anchors, index: pd.DatetimeIndex) -> np.ndarray:
    xs = [pd.Period(m, "M").ordinal for m, _ in anchors]
    out = np.empty(len(index))
    for i, p in enumerate(index.to_period("M")):
        k = max(j for j, x in enumerate(xs) if x <= p.ordinal)
        out[i] = anchors[k][1]
    return out


def history(rng: np.random.Generator) -> pd.DataFrame:
    """Monthly macro history, January 2016 to December 2025."""
    idx = HISTORY
    n = len(idx)
    u = _interpolate(UNEMPLOYMENT, idx) + rng.normal(0, 0.06, n)
    gdp = _interpolate(GDP_GROWTH, idx) + rng.normal(0, 0.15, n)
    hpi = _interpolate(HOUSE_PRICES, idx) * np.exp(rng.normal(0, 0.003, n))
    cars = _interpolate(USED_CARS, idx) * np.exp(rng.normal(0, 0.004, n))
    cpi = _interpolate(INFLATION, idx) + rng.normal(0, 0.08, n)
    return pd.DataFrame({
        "month": idx.date,
        "unemployment_pct": np.round(u, 2),
        "policy_rate_pct": _steps(POLICY_RATE, idx),
        "gdp_growth_pct": np.round(gdp, 2),
        "house_price_index": np.round(hpi, 2),
        "used_car_index": np.round(cars, 2),
        "inflation_pct": np.round(cpi, 2),
    })


# Forward-looking scenarios, as Fernhill's economics team published them for the
# December 2025 reporting date. Weights are the team's; IFRS 9 needs them, CECL does not.
SCENARIOS = {
    #            weight   unemployment anchors                  rate anchors           HPI change, GDP trough
    "base":     (0.40, [("2025-12", 5.0), ("2026-12", 4.9), ("2030-12", 4.7)],
                 [("2025-12", 3.75), ("2026-06", 3.50), ("2030-12", 3.25)], 0.10, 1.4),
    "upside":   (0.15, [("2025-12", 5.0), ("2026-12", 4.5), ("2030-12", 4.3)],
                 [("2025-12", 3.75), ("2026-06", 3.75), ("2030-12", 3.50)], 0.16, 2.4),
    "downside": (0.30, [("2025-12", 5.0), ("2027-03", 7.4), ("2028-12", 6.1), ("2030-12", 5.4)],
                 [("2025-12", 3.75), ("2026-09", 2.50), ("2030-12", 2.75)], -0.08, -1.6),
    "severe":   (0.15, [("2025-12", 5.0), ("2027-06", 10.4), ("2029-06", 7.6), ("2030-12", 6.2)],
                 [("2025-12", 3.75), ("2026-09", 1.00), ("2030-12", 1.50)], -0.24, -5.2),
    # The supervisor's 2026 stress scenario: stagflation, rates up, not down.
    "stress_2026": (None, [("2025-12", 5.0), ("2027-03", 9.1), ("2028-12", 7.8), ("2030-12", 6.4)],
                    [("2025-12", 3.75), ("2026-06", 5.50), ("2027-03", 6.50), ("2028-12", 5.00),
                     ("2030-12", 4.00)], -0.29, -4.4),
}


def scenarios(hist: pd.DataFrame) -> pd.DataFrame:
    idx = FORWARD
    last_hpi = float(hist["house_price_index"].iloc[-1])
    last_car = float(hist["used_car_index"].iloc[-1])
    rows = []
    t = np.arange(1, len(idx) + 1)
    for name, (weight, u_anchor, r_anchor, hpi_change, gdp_trough) in SCENARIOS.items():
        u = _interpolate(u_anchor, idx)
        r = _interpolate(r_anchor, idx)
        # House prices reach their trough (or peak) after two years, then grow 2% a year.
        path = np.where(t <= 24, hpi_change * t / 24, hpi_change + 0.02 * (t - 24) / 12)
        hpi = last_hpi * (1 + path)
        cars = last_car * (1 + 0.6 * np.where(t <= 24, hpi_change * t / 24, hpi_change))
        gdp = np.interp(t, [0, 12, 24, 60], [1.6, gdp_trough, 1.5, 1.8])
        for i, m in enumerate(idx):
            rows.append((dt.date(2025, 12, 31), name, weight, m.date(), round(u[i], 2),
                         round(r[i], 2), round(gdp[i], 2), round(hpi[i], 2), round(cars[i], 2)))
    return pd.DataFrame(rows, columns=["as_of", "scenario", "weight", "month",
                                       "unemployment_pct", "policy_rate_pct", "gdp_growth_pct",
                                       "house_price_index", "used_car_index"])


def stress_factor(hist: pd.DataFrame) -> np.ndarray:
    """The macro driver of retail delinquency, one value a month: unemployment's level
    above its calm-times norm, plus how fast it has risen over the past year. From April
    2020 to June 2021 government income support (furlough, grants) absorbed about half
    of what unemployment would otherwise have done to borrowers."""
    u = hist["unemployment_pct"].to_numpy()
    rise = u - np.concatenate([np.full(12, u[0]), u[:-12]])
    s = 0.20 * (u - 4.6) + 0.12 * np.maximum(rise, 0.0)
    support = np.zeros(len(u))
    support[51:66] = 0.5
    return s * (1 - support)
