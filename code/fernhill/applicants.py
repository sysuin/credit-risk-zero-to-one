"""Consumer applicants: who walks through Fernhill's door, what the bureau says about them,
and what Fernhill decided.

Every applicant has a latent creditworthiness `z` (standard normal; higher is safer). It
drives everything observable about them, noisily, and it drives how they will actually
behave. Fernhill never sees `z`; the truth database keeps it.

Fernhill's decisions follow its history, written in DECISIONS.md §5: policy rules, the
Mark I scorecard of 2015 with a cut-off that moved five times, a refer band worked by
underwriters, a few overrides, flat prices until 2019 and risk-based tiers after.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REGIONS = ["Northgate", "Riverside", "Eastvale", "Westmoor", "Central", "Harbourside"]
# Regional unemployment sensitivity and income level relative to the country.
REGION_MACRO = np.array([1.25, 1.00, 0.90, 1.10, 0.85, 1.05])
REGION_INCOME = np.array([-0.08, 0.00, 0.04, -0.05, 0.12, 0.02])
REGION_SHARE = np.array([0.15, 0.20, 0.17, 0.13, 0.22, 0.13])

PRODUCTS = ("personal", "card", "auto", "mortgage")

# Applications a year, before seasonality and the 2020 dip.
VOLUME = {"personal": (6200, 9800), "card": (4300, 6400), "auto": (2900, 4200),
          "mortgage": (700, 1100)}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def annuity(principal, annual_rate_pct, months):
    r = np.asarray(annual_rate_pct, dtype=float) / 1200.0
    months = np.asarray(months, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        pay = np.where(r > 0, principal * r / (1 - (1 + r) ** -months), principal / months)
    return pay


def application_dates(product: str, rng: np.random.Generator) -> np.ndarray:
    """One date per application, 2016-01-01 to 2025-12-31."""
    lo, hi = VOLUME[product]
    out = []
    for year in range(2016, 2026):
        base = lo + (hi - lo) * (year - 2016) / 9
        for month in range(1, 13):
            season = {"personal": [1.25, 1.05, 1.0, 1.0, 0.95, 0.95, 1.0, 0.95, 0.95, 1.0, 0.95, 0.95],
                      "card": [0.9, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 1.1, 1.0],
                      "auto": [0.85, 0.95, 1.3, 1.1, 1.05, 1.0, 0.95, 0.95, 1.15, 0.95, 0.85, 0.85],
                      "mortgage": [0.8, 0.9, 1.05, 1.1, 1.1, 1.1, 1.05, 1.0, 1.0, 1.0, 0.95, 0.85],
                      }[product][month - 1]
            shock = 1.0
            if year == 2020 and month in (4, 5):
                shock = 0.45
            elif year == 2020 and month in (6, 7, 8):
                shock = 0.75
            elif year == 2021 and product in ("personal", "card") and month >= 2:
                shock = 1.18          # the growth push: brokers and online campaigns
            elif year == 2022 and month <= 6 and product in ("personal", "card"):
                shock = 1.15
            elif year == 2023 and product == "mortgage":
                shock = 0.7           # rates up, mortgage demand down
            n = rng.poisson(base / 12 * season * shock)
            days = pd.Timestamp(year, month, 1).days_in_month
            d = rng.integers(1, days + 1, n)
            out.append(pd.to_datetime(dict(year=np.full(n, year), month=np.full(n, month), day=d)))
    dates = pd.concat([pd.Series(x) for x in out], ignore_index=True)
    return np.sort(dates.to_numpy())


def make_applicants(product: str, dates: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    n = len(dates)
    d = pd.DatetimeIndex(dates)
    year = d.year.to_numpy()
    ym = d.year.to_numpy() * 12 + d.month.to_numpy()

    # Channel mix moves online over the decade; brokers (and car dealers for auto) grow
    # during the growth push.
    online_share = np.clip(0.18 + 0.05 * (year - 2016), 0.18, 0.62)
    broker_share = np.where((ym >= 2021 * 12 + 2) & (ym <= 2022 * 12 + 6), 0.36, 0.17)
    if product == "auto":
        broker_share = np.full(n, 0.62)
        online_share = online_share * 0.5
    if product == "mortgage":
        broker_share = np.full(n, 0.45)
    u = rng.random(n)
    channel = np.where(u < broker_share, "broker",
                       np.where(u < broker_share + online_share * (1 - broker_share), "online", "branch"))
    if product == "auto":
        channel = np.where(channel == "broker", "dealer", channel)

    # Latent creditworthiness. The pool is a little worse in the 2020 shock, and the
    # growth push and broker channels bring in more credit-hungry applicants.
    shift = np.zeros(n)
    shift -= np.where((ym >= 2020 * 12 + 4) & (ym <= 2020 * 12 + 12), 0.15, 0.0)
    shift -= np.where(np.isin(channel, ["broker"]), 0.30, 0.0)
    push = (ym >= 2021 * 12 + 2) & (ym <= 2022 * 12 + 6) & (product in ("personal", "card"))
    shift -= np.where(push & (channel != "branch"), 0.35, 0.0)
    shift += {"mortgage": 0.55, "auto": 0.15, "card": 0.0, "personal": -0.05}[product]
    z = rng.normal(0, 1, n) + shift

    age = np.clip(np.round(rng.normal(40 + 3 * z.clip(-2, 2), 12.5)), 18, 79).astype(int)
    if product == "mortgage":
        age = np.clip(np.round(rng.normal(37 + 2 * z.clip(-2, 2), 8)), 21, 69).astype(int)
    region_idx = rng.choice(len(REGIONS), n, p=REGION_SHARE)

    # Gender, collected for monitoring only. Incomes differ by gender on average, as they
    # do in most economies; behaviour given income and z does not.
    g = rng.random(n)
    gender = np.where(g < 0.485, "F", np.where(g < 0.965, "M", np.where(g < 0.975, "X", "U")))
    gender_income = np.where(gender == "F", -0.11, 0.0)

    age_curve = -0.0009 * (age - 47) ** 2 + 0.25
    log_income = (10.55 + 0.22 * z + age_curve + REGION_INCOME[region_idx] + gender_income
                  + 0.025 * (year - 2016) + rng.normal(0, 0.42, n))
    if product == "mortgage":
        log_income += 0.35
    income = np.exp(log_income)

    emp_u = rng.random(n)
    p_self = 0.11 + 0.03 * (z < -0.5)
    p_retired = np.where(age >= 62, 0.65, 0.01)
    p_part = 0.07
    p_unemp = np.clip(0.04 - 0.02 * z, 0.0, 0.10)
    emp = np.where(emp_u < p_retired, "retired",
          np.where(emp_u < p_retired + p_self, "self_employed",
          np.where(emp_u < p_retired + p_self + p_part, "part_time",
          np.where(emp_u < p_retired + p_self + p_part + p_unemp, "other", "employed"))))
    income = np.where(emp == "part_time", income * 0.55, income)
    income = np.where(emp == "other", income * 0.45, income)
    income = np.where(emp == "retired", income * 0.7, income)
    emp_months = np.where(np.isin(emp, ["retired", "other"]), 0,
                          np.round(rng.exponential(np.clip(30 + 20 * z, 6, 120) * np.clip((age - 17) / 20, 0.2, 2.0))))
    emp_months = np.minimum(emp_months, (age - 17) * 12).astype(int)

    h = rng.random(n)
    p_own = np.clip(0.05 + 0.006 * (age - 18) + 0.03 * z, 0.01, 0.5)
    p_mort = np.clip(0.10 + 0.012 * (age - 22) + 0.06 * z, 0.02, 0.55) * (age < 70)
    p_family = np.clip(0.45 - 0.03 * (age - 18), 0.0, 0.45)
    housing = np.where(h < p_own, "owner",
              np.where(h < p_own + p_mort, "mortgage",
              np.where(h < p_own + p_mort + p_family, "with_family", "renter")))
    if product == "mortgage":
        housing = np.where(rng.random(n) < 0.35, "mortgage", np.where(rng.random(n) < 0.3, "with_family", "renter"))
    addr_months = np.round(rng.exponential(np.clip(24 + 12 * z + 1.5 * (age - 25), 6, 240))).astype(int)
    addr_months = np.minimum(addr_months, (age - 16) * 12)
    dependants = np.minimum(rng.poisson(np.where((age > 25) & (age < 55), 1.1, 0.3)), 5)

    # The credit bureau. Young applicants are more often unknown to it.
    hit = rng.random(n) < np.clip(0.97 - 0.30 * (age < 23) - 0.08 * (age < 27), 0.5, 0.99)
    raw = 0.95 * z + 0.012 * (age - 40) + rng.normal(0, 0.45, n)
    score_v2 = np.clip(np.round(610 + 72 * raw), 300, 850)
    # On 1 July 2019 the bureau moved to version 3 of its score: same people, new scale.
    v3 = d >= pd.Timestamp("2019-07-01")
    score_v3 = np.clip(np.round(645 + 80 * raw), 300, 850)
    bureau_score = np.where(v3, score_v3, score_v2)
    oldest = np.where(hit, np.round(np.clip(rng.normal((age - 18) * 12 * 0.75, 30), 1, (age - 17) * 12)), 0).astype(int)
    oldest = np.where(hit & (rng.random(n) < 0.06), np.minimum(oldest, rng.integers(1, 12, n)), oldest)
    open_accounts = np.where(hit, rng.poisson(np.clip(3.2 + 0.5 * z + 0.04 * (age - 30), 0.5, 9)), 0)
    utilisation = np.where(hit, np.clip(rng.beta(2, 3, n) + (-0.13 * z) + rng.normal(0, 0.08, n), 0.0, 1.15), np.nan)
    revolving_limit = np.where(hit, np.round(np.exp(np.log(income) - 1.5 + 0.3 * z + rng.normal(0, 0.5, n)), -2), 0)
    revolving_balance = np.where(hit, np.round(revolving_limit * np.nan_to_num(utilisation), -1), 0)
    enquiries = np.where(hit, rng.poisson(np.exp(0.15 - 0.55 * z + 0.25 * (channel == "broker"))), 0)
    ws = rng.random(n)
    p90 = sigmoid(-3.6 - 1.6 * z)
    p60 = sigmoid(-3.1 - 1.3 * z)
    p30 = sigmoid(-2.0 - 1.0 * z)
    worst = np.where(~hit, 0, np.where(ws < p90, 90, np.where(ws < p90 + p60, 60, np.where(ws < p90 + p60 + p30, 30, 0))))
    public_records = np.where(hit, rng.poisson(sigmoid(-4.0 - 1.5 * z) * 1.5), 0)
    other_payments = np.round(np.where(hit, np.nan_to_num(revolving_balance) * 0.03
                                       + rng.exponential(income / 12 * np.clip(0.08 - 0.03 * z, 0.01, 0.2)), 0), 0)
    if product != "mortgage":
        other_payments = other_payments + np.where(np.isin(housing, ["mortgage"]), income / 12 * 0.18, 0)

    # Open banking: the applicant lets Fernhill read twelve months of their current
    # account. Offered online from 2021, and in branches from 2023.
    offered = (((channel == "online") & (d >= pd.Timestamp("2021-03-01")))
               | ((channel == "branch") & (d >= pd.Timestamp("2023-01-01"))))
    consent = offered & (rng.random(n) < np.clip(0.55 + 0.1 * z, 0.2, 0.85))
    ob_balance = np.where(consent, np.round(np.exp(np.log(income) - 3.2 + 0.55 * z + rng.normal(0, 0.6, n))), np.nan)
    ob_overdraft_days = np.where(consent, np.clip(np.round(rng.exponential(np.exp(1.6 - 0.9 * z))), 0, 90), np.nan)
    ob_volatility = np.where(consent, np.round(np.clip(rng.gamma(2.0, 0.07, n) * np.exp(-0.2 * z) + 0.25 * (emp == "self_employed"), 0.01, 1.5), 3), np.nan)
    ob_returned = np.where(consent, rng.poisson(np.exp(-1.6 - 1.0 * z)), np.nan)
    ob_betting = np.where(consent, np.round(np.clip(rng.exponential(0.006, n) * np.exp(-0.5 * z) * (rng.random(n) < 0.25), 0, 0.3), 4), np.nan)

    # Fraud: a small share of applications are made to be taken and never repaid, by
    # someone using a stolen or invented identity. More of them come in online.
    p_fraud = 0.004 + 0.008 * (channel == "online") * (year >= 2021)
    fraud = rng.random(n) < p_fraud
    oldest = np.where(fraud, np.minimum(oldest, rng.integers(3, 30, n)), oldest)
    addr_months = np.where(fraud, rng.integers(1, 9, n), addr_months)
    enquiries = np.where(fraud, enquiries + rng.integers(2, 6, n), enquiries)
    consent = consent & ~fraud
    for col in (ob_balance, ob_overdraft_days, ob_volatility, ob_returned, ob_betting):
        col[fraud] = np.nan

    # Stated income. Brokers' applicants (and the self-employed) round theirs up unless
    # it is checked. Fraud states a comfortable income.
    inflate = np.where(np.isin(channel, ["broker", "dealer"]), rng.lognormal(0.12, 0.12, n), rng.lognormal(0.01, 0.05, n))
    inflate = np.where(emp == "self_employed", inflate * rng.lognormal(0.08, 0.08, n), inflate)
    stated_income = np.round(income * np.maximum(inflate, 1.0), -2)
    stated_income = np.where(fraud, np.round(rng.uniform(48000, 90000, n), -3), stated_income)

    return pd.DataFrame({
        "app_date": d.date, "channel": channel, "age": age, "region": np.array(REGIONS)[region_idx],
        "region_idx": region_idx, "gender": gender,
        "true_income": income, "stated_income": stated_income,
        "employment": emp, "employment_months": emp_months, "housing": housing,
        "address_months": addr_months, "dependants": dependants,
        "bureau_hit": hit, "bureau_score": np.where(hit, bureau_score, np.nan),
        "bureau_version": np.where(hit, np.where(v3, "v3", "v2"), None),
        "oldest_account_months": oldest, "open_accounts": open_accounts,
        "revolving_balance": revolving_balance, "revolving_utilisation": np.round(utilisation, 3),
        "enquiries_6m": enquiries, "worst_status_24m": worst, "public_records": public_records,
        "other_payments": other_payments,
        "ob_consent": consent, "ob_avg_balance": ob_balance, "ob_overdraft_days": ob_overdraft_days,
        "ob_income_volatility": ob_volatility, "ob_returned_payments": ob_returned,
        "ob_betting_share": ob_betting,
        "z": z, "fraud": fraud,
    })


def requested_terms(product: str, a: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    n = len(a)
    inc = a["stated_income"].to_numpy()
    if product == "personal":
        amount = np.clip(np.round(np.exp(np.log(inc) - 1.6 + rng.normal(0, 0.55, n)), -2), 1000, 40000)
        term = rng.choice([12, 24, 36, 48, 60], n, p=[0.08, 0.22, 0.34, 0.18, 0.18])
        purpose = rng.choice(["debt_consolidation", "home_improvement", "car", "wedding", "holiday", "other"],
                             n, p=[0.38, 0.22, 0.14, 0.05, 0.06, 0.15])
        collateral = np.full(n, np.nan)
        deposit = np.zeros(n)
    elif product == "card":
        amount = np.zeros(n)            # a card applicant asks for a card; Fernhill sets the limit
        term = np.zeros(n, dtype=int)
        purpose = np.full(n, "card")
        collateral = np.full(n, np.nan)
        deposit = np.zeros(n)
    elif product == "auto":
        price = np.clip(np.round(np.exp(np.log(inc) - 0.55 + rng.normal(0, 0.35, n)), -2), 4000, 90000)
        deposit = np.round(price * np.clip(rng.beta(2, 9, n) + 0.04 * a["z"].to_numpy().clip(-2, 2), 0, 0.5), -2)
        amount = price - deposit
        term = rng.choice([36, 48, 60, 72], n, p=[0.18, 0.30, 0.37, 0.15])
        purpose = np.where(rng.random(n) < 0.68, "used_car", "new_car")
        collateral = price
    else:
        price = np.clip(np.round(np.exp(np.log(inc) + 1.45 + rng.normal(0, 0.25, n)), -3), 80000, 1500000)
        ltv = np.clip(rng.beta(7, 2.6, n) * 0.97 + 0.02 * (a["channel"].to_numpy() == "broker"), 0.35, 0.95)
        amount = np.round(price * ltv, -3)
        deposit = price - amount
        term = rng.choice([240, 300, 360], n, p=[0.15, 0.45, 0.40])
        purpose = np.where(a["housing"].to_numpy() == "mortgage", "remortgage", "purchase")
        collateral = price
    return pd.DataFrame({"amount_requested": amount, "term_requested": term, "purpose": purpose,
                         "collateral_value": collateral, "deposit": deposit})


# ---------------------------------------------------------------------------------------
# Fernhill's decisions

# The Mark I scorecard (2015). A points table, as a scorecard is: a base of 140 points
# plus the points for each characteristic. Its bureau points were set on version 2 of the
# bureau score.
def mark1_score(a: pd.DataFrame, monthly_payment: np.ndarray) -> np.ndarray:
    bs = a["bureau_score"].to_numpy()
    pts = 140 + np.where(np.isnan(bs), 38,
          np.select([bs < 520, bs < 560, bs < 600, bs < 640, bs < 680, bs < 720, bs < 760],
                    [0, 22, 41, 58, 74, 90, 104], 116))
    util = np.nan_to_num(a["revolving_utilisation"].to_numpy(), nan=0.5)
    pts += np.select([util < 0.15, util < 0.4, util < 0.7, util < 0.95], [62, 55, 44, 30], 18)
    enq = a["enquiries_6m"].to_numpy()
    pts += np.select([enq == 0, enq == 1, enq <= 3], [60, 54, 44], 29)
    ws = a["worst_status_24m"].to_numpy()
    pts += np.select([ws == 0, ws == 30, ws == 60], [58, 38, 22], 6)
    inc = a["stated_income"].to_numpy() / 12
    dti = (a["other_payments"].to_numpy() + monthly_payment) / np.maximum(inc, 1)
    pts += np.select([dti < 0.15, dti < 0.25, dti < 0.35, dti < 0.45], [60, 54, 45, 34], 22)
    em = a["employment_months"].to_numpy()
    emp = a["employment"].to_numpy()
    pts += np.where(emp == "retired", 52, np.select([em < 6, em < 24, em < 60], [30, 42, 50], 58))
    hs = a["housing"].to_numpy()
    pts += np.select([hs == "owner", hs == "mortgage", hs == "with_family"], [62, 56, 44], 40)
    am = a["address_months"].to_numpy()
    pts += np.select([am < 12, am < 36, am < 96], [38, 46, 53], 58)
    age = a["age"].to_numpy()
    pts += np.select([age < 25, age < 35, age < 50], [36, 44, 50], 54)
    return pts.astype(int)


# The cut-off history, the one the chapters keep returning to.
CUTOFFS = [  # (from, Mark I cut-off for personal loans and cards, DTI limit)
    ("2016-01-01", 560, 0.50),
    ("2019-01-01", 575, 0.50),
    ("2020-04-01", 610, 0.45),   # the shock: tighten everything
    ("2021-02-01", 525, 0.55),   # the growth push
    ("2022-07-01", 580, 0.50),   # back to normal, a little tighter than before
]
PRODUCT_CUTOFF_OFFSET = {"personal": 0, "card": 5, "auto": -15, "mortgage": -5}


def policy_for(dates: pd.DatetimeIndex):
    cut = np.zeros(len(dates))
    dti = np.zeros(len(dates))
    for start, c, dl in CUTOFFS:
        m = dates >= pd.Timestamp(start)
        cut[m] = c
        dti[m] = dl
    return cut, dti


def base_rate(product: str, dates: pd.DatetimeIndex, policy_rate: np.ndarray, score: np.ndarray,
              rng: np.random.Generator) -> np.ndarray:
    """The rate Fernhill offered, by its pricing policy of the day."""
    risk_based = dates >= pd.Timestamp("2019-04-01")
    if product == "personal":
        flat = np.full(len(dates), 10.9)
        tier = np.select([score >= 660, score >= 630, score >= 600], [6.9, 9.4, 12.9], 17.9)
    elif product == "card":
        flat = np.full(len(dates), 22.9)
        tier = np.select([score >= 650, score >= 615], [18.9, 22.9], 27.9)
    elif product == "auto":
        flat = np.full(len(dates), 7.9)
        tier = np.select([score >= 650, score >= 610], [5.9, 7.9], 11.9)
    else:
        # Mortgages are priced off the policy rate: a margin of two points, at least 2.5%.
        flat = np.maximum(policy_rate + 2.0, 2.5)
        tier = flat
        risk_based = np.zeros(len(dates), dtype=bool)
    rate = np.where(risk_based, tier, flat)
    # Funding costs pass through, most of the way, as the policy rate moves off 0.5%.
    pass_through = {"personal": 0.8, "card": 0.3, "auto": 0.85, "mortgage": 0.0}[product]
    rate = rate + pass_through * (policy_rate - 0.5)
    return np.round(rate, 2)


def decide(product: str, a: pd.DataFrame, policy_rate: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    n = len(a)
    d = pd.DatetimeIndex(pd.to_datetime(a["app_date"]))
    req = a["amount_requested"].to_numpy()
    term = a["term_requested"].to_numpy()

    if product == "card":
        provisional_rate = np.full(n, 22.9)
        provisional_pay = np.zeros(n)
    elif product == "mortgage":
        provisional_rate = np.maximum(policy_rate + 2.0, 2.5)
        provisional_pay = annuity(req, provisional_rate + 3.0, term)   # affordability stress
    else:
        provisional_rate = np.full(n, 10.9 if product == "personal" else 7.9)
        provisional_pay = annuity(req, provisional_rate, term)
    score = mark1_score(a, provisional_pay)
    cut, dti_limit = policy_for(d)
    cut = cut + PRODUCT_CUTOFF_OFFSET[product]
    inc_m = a["stated_income"].to_numpy() / 12
    dti = (a["other_payments"].to_numpy() + provisional_pay) / np.maximum(inc_m, 1)

    reason = np.full(n, None, dtype=object)
    reason = np.where(a["worst_status_24m"].to_numpy() >= 90, "recent_serious_arrears", reason)
    reason = np.where((reason == None) & (a["public_records"].to_numpy() > 0), "public_record", reason)  # noqa: E711
    thin = (~a["bureau_hit"].to_numpy()) & (a["age"].to_numpy() < 25)
    reason = np.where((reason == None) & thin, "thin_file", reason)  # noqa: E711
    if product == "mortgage":
        ltv = req / a["collateral_value"].to_numpy()
        reason = np.where((reason == None) & (ltv > 0.95), "ltv_over_limit", reason)  # noqa: E711
        reason = np.where((reason == None) & (dti > 0.45), "affordability", reason)  # noqa: E711
    else:
        reason = np.where((reason == None) & (dti > dti_limit), "affordability", reason)  # noqa: E711
    policy_ok = reason == None  # noqa: E711

    approve = policy_ok & (score >= cut + 10)
    refer = policy_ok & (score >= cut - 10) & (score < cut + 10)
    # Underwriters work the refer band. Their judgement sees a little of what the
    # scorecard does not (they phone employers, read bank statements).
    uw_view = a["z"].to_numpy() + rng.normal(0, 1.1, n) + (score - cut) / 25
    uw_approve = refer & (uw_view > 0.1)
    # During the growth push the refer band went to "instant decision": approved unseen.
    push = (d >= pd.Timestamp("2021-02-01")) & (d < pd.Timestamp("2022-07-01")) & (product in ("personal", "card"))
    uw_approve = uw_approve | (refer & push)
    decline_score = policy_ok & (score < cut - 10)
    reason = np.where(decline_score | (refer & ~uw_approve), "score_below_cutoff", reason)
    approved = approve | uw_approve
    # Overrides: branch managers approve a few declines (the low-side override); credit
    # officers decline a few approvals (the high-side override).
    low_side = (~approved) & (reason == "score_below_cutoff") & (rng.random(n) < 0.03) & (a["channel"].to_numpy() == "branch")
    high_side = approved & (rng.random(n) < 0.008)
    approved = (approved | low_side) & ~high_side
    override = np.where(low_side, "low_side", np.where(high_side, "high_side", None))
    reason = np.where(low_side, None, reason)
    reason = np.where(high_side, "credit_officer", reason)
    # Fraud checks catch some of the fraud before a decision.
    catch_rate = np.where(d >= pd.Timestamp("2023-06-01"), 0.55, np.where(push, 0.12, 0.30))
    caught = a["fraud"].to_numpy() & (rng.random(n) < catch_rate)
    reason = np.where(caught, "fraud_check", reason)
    approved = approved & ~caught

    decision = np.where(approved, "approve", "decline")
    rate = base_rate(product, d, policy_rate, score, rng)
    # A randomised price test in 2024: one approved personal loan applicant in ten was
    # quoted 1.5 points above or below the policy price, at random.
    test = (product == "personal") & (d >= pd.Timestamp("2024-01-01")) & (d < pd.Timestamp("2025-01-01"))
    arm = np.where(test & (rng.random(n) < 0.10), np.where(rng.random(n) < 0.5, "minus_150", "plus_150"), None)
    rate = rate + np.where(arm == "minus_150", -1.5, 0.0) + np.where(arm == "plus_150", 1.5, 0.0)

    if product == "card":
        limit = np.round(np.clip(a["stated_income"].to_numpy() * np.select([score >= 660, score >= 620], [0.18, 0.12], 0.07), 500, 20000), -2)
        offered_amount = np.where(approved, limit, np.nan)
        offered_term = np.zeros(n, dtype=int)
    else:
        # Approved for less than asked when affordability is tight.
        cap = np.where(dti > dti_limit * 0.9, 0.8, 1.0)
        offered_amount = np.where(approved, np.round(req * cap, -2), np.nan)
        offered_term = term
    return pd.DataFrame({"mark1_score": score, "cutoff": cut, "decision": decision,
                         "decline_reason": np.where(approved, None, reason), "override": override,
                         "offered_rate": np.where(approved, np.round(rate, 2), np.nan),
                         "offered_amount": offered_amount, "offered_term": offered_term,
                         "price_test_arm": np.where(approved, arm, None), "dti_at_decision": np.round(dti, 3)})


def take_up(product: str, a: pd.DataFrame, dec: pd.DataFrame, policy_rate: np.ndarray,
            rng: np.random.Generator) -> np.ndarray:
    """Whether an approved applicant took the loan. Good applicants have better offers
    elsewhere, so they walk away from a high price more readily: adverse selection."""
    z = a["z"].to_numpy()
    rate = dec["offered_rate"].to_numpy()
    market = {"personal": 9.0, "card": 21.0, "auto": 7.0, "mortgage": 3.2}[product]
    pass_through = {"personal": 0.8, "card": 0.3, "auto": 0.85, "mortgage": 0.7}[product]
    market_for_them = market + pass_through * (policy_rate - 0.5) - 1.2 * z.clip(-2.5, 2.5)
    if product == "mortgage":
        market_for_them = market + 0.95 * np.maximum(policy_rate - 0.5, 0) - 0.4 * z.clip(-2.5, 2.5)
    gap = rate - market_for_them
    sens = {"personal": 0.45, "card": 0.25, "auto": 0.6, "mortgage": 1.4}[product]
    sens = sens * np.where(a["channel"].to_numpy() == "broker", 1.5, 1.0)
    p = sigmoid(2.2 - sens * gap)
    p = np.where(a["fraud"].to_numpy(), 0.98, p)
    return (dec["decision"].to_numpy() == "approve") & (rng.random(len(a)) < p)
