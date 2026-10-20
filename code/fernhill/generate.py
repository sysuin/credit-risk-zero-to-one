#!/usr/bin/env python3
"""Generate Fernhill Bank's loan book from its seed.

    python code/fernhill/generate.py

Writes `data/fernhill/loanbook.duckdb` (what Fernhill's systems hold) and
`data/fernhill/truth.duckdb` (what only the simulator knows). Same seed, same bytes of
data, on every machine: every random draw comes from one generator, in a fixed order.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time

import duckdb
import numpy as np
import pandas as pd

from ballast.config import FERNHILL, LOANBOOK, SEED, TRUTH
from fernhill import applicants as ap
from fernhill import business as bz
from fernhill import corporate, economy, engine, recovery

PREFIX = {"personal": "PL", "card": "CC", "auto": "AL", "mortgage": "MG",
          "sme_term": "BT", "sme_overdraft": "BO", "sme_emergency": "BE"}
MIGRATION_T = 74               # March 2022: the card book moves to a new processor


def month_index(dates) -> np.ndarray:
    d = pd.DatetimeIndex(pd.to_datetime(dates))
    return ((d.year - 2016) * 12 + d.month - 1).to_numpy()


def cents(x) -> np.ndarray:
    return np.round(np.nan_to_num(np.asarray(x, dtype=float)) * 100).astype(np.int64)


def main() -> int:
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    macro = economy.history(rng)
    scen = economy.scenarios(macro)
    base = scen[scen.scenario == "base"]
    u_all = np.concatenate([macro["unemployment_pct"].to_numpy(), base["unemployment_pct"].to_numpy()])
    stress_all = economy.stress_factor(pd.DataFrame({"unemployment_pct": u_all}))
    stress, fwd_stress = stress_all[:120], stress_all[120:]
    fwd_rate = base["policy_rate_pct"].to_numpy()
    policy_by_t = macro["policy_rate_pct"].to_numpy()
    log("economy", t0)

    # ---------------------------------------------------------------- consumer applications
    apps, accts = [], []
    app_seq = 0
    for product in ap.PRODUCTS:
        dates = ap.application_dates(product, rng)
        a = ap.make_applicants(product, dates, rng)
        a = pd.concat([a, ap.requested_terms(product, a, rng)], axis=1)
        mt = month_index(a["app_date"])
        pr = policy_by_t[mt]
        dec = ap.decide(product, a, pr, rng)
        took = ap.take_up(product, a, dec, pr, rng)
        open_date = (pd.to_datetime(a["app_date"]) + pd.to_timedelta(rng.integers(3, 26, len(a)), unit="D")).dt.date
        open_t = month_index(open_date)
        pending = took & (open_t > 119)
        booked = took & ~pending
        n = len(a)
        app_ids = np.array([f"A{app_seq + i + 1:08d}" for i in range(n)])
        app_seq += n
        outcome = np.where(booked, "booked", np.where(pending, "offer_open",
                           np.where(dec["decision"] == "approve", "not_taken_up", "declined")))
        a["app_id"] = app_ids
        a["product"] = product
        a["outcome"] = outcome
        a["open_date"] = np.where(booked, open_date, None)
        a = pd.concat([a, dec], axis=1)
        apps.append(a)

        # Accounts: booked loans, plus shadow accounts for declined and walked-away
        # applicants, run for twelve months so the truth knows how they would have done.
        shadow = outcome != "booked"
        shadow &= outcome != "offer_open"
        sel = booked | shadow
        s = a[sel].reset_index(drop=True)
        k = len(s)
        is_shadow = shadow[sel]
        if product == "card":
            amount = np.where(is_shadow, np.round(np.clip(s["stated_income"] * 0.08, 500, 6000), -2), s["offered_amount"])
            term = np.zeros(k, dtype=int)
        else:
            amount = np.where(is_shadow, s["amount_requested"], s["offered_amount"])
            term = np.where(is_shadow, s["term_requested"], s["offered_term"]).astype(int)
        policy_rate_at = policy_by_t[np.minimum(month_index(s["app_date"]), 119)]
        std_rate = ap.base_rate(product, pd.DatetimeIndex(pd.to_datetime(s["app_date"])), policy_rate_at,
                                s["mark1_score"].to_numpy(), rng)
        rate = np.where(is_shadow, std_rate, s["offered_rate"])
        if product == "mortgage":
            u = rng.random(k)
            rate_type = np.where(u < 0.35, "fixed_then_variable", np.where(u < 0.6, "variable", "fixed"))
            fixed_months = np.where(rate_type == "fixed_then_variable", np.where(rng.random(k) < 0.6, 24, 60), 0)
            margin = np.where(rate_type == "variable", rate - policy_rate_at, 2.5)
        elif product == "card":
            rate_type = np.full(k, "variable")
            fixed_months = np.zeros(k, dtype=int)
            margin = rate - policy_rate_at
        else:
            rate_type = np.full(k, "fixed")
            fixed_months = np.zeros(k, dtype=int)
            margin = np.zeros(k)
        o_t = np.where(is_shadow, np.minimum(month_index(s["app_date"]), 119),
                       month_index(pd.to_datetime(s["open_date"].where(~is_shadow, s["app_date"]))))
        accts.append(pd.DataFrame({
            "app_id": s["app_id"], "product": product, "open_t": o_t, "amount": amount.astype(float),
            "term": term, "rate": rate.astype(float), "rate_type": rate_type, "fixed_months": fixed_months,
            "margin": margin, "z": s["z"], "income": s["true_income"] / 12, "other_payments": s["other_payments"],
            "fraud": s["fraud"], "macro_sens": ap.REGION_MACRO[s["region_idx"].to_numpy()],
            "shock_2020": np.full(k, 0.35), "holiday_free": 0, "shadow": is_shadow,
            "secured": product in ("auto", "mortgage"), "collateral": s["collateral_value"],
            "region": s["region"], "channel": s["channel"],
        }))
        log(f"{product}: {n} applications, {booked.sum()} booked", t0)

    # ---------------------------------------------------------------- small business
    biz = bz.make_businesses(3800, rng)
    sa = bz.make_applications(biz, rng)
    mt = month_index(sa["app_date"])
    sdec = bz.decide(sa, policy_by_t[mt], rng)
    stook = bz.take_up(sa, sdec, rng)
    s_open = (pd.to_datetime(sa["app_date"]) + pd.to_timedelta(rng.integers(5, 30, len(sa)), unit="D")).dt.date
    s_open_t = month_index(s_open)
    s_pending = stook & (s_open_t > 119)
    s_booked = stook & ~s_pending
    sa["app_id"] = [f"S{i + 1:07d}" for i in range(len(sa))]
    sa["outcome"] = np.where(s_booked, "booked", np.where(s_pending, "offer_open",
                             np.where(sdec["decision"] == "approve", "not_taken_up", "declined")))
    sa["open_date"] = np.where(s_booked, s_open, None)
    sa = pd.concat([sa, sdec], axis=1)
    sb = sa[s_booked].reset_index(drop=True)
    k = len(sb)
    prod = sb["product"].to_numpy()
    accts.append(pd.DataFrame({
        "app_id": sb["app_id"], "product": prod, "open_t": month_index(sb["open_date"]),
        "amount": sb["offered_amount"].astype(float), "term": sb["term_requested"].astype(int),
        "rate": sb["offered_rate"].astype(float),
        "rate_type": np.where(prod == "sme_emergency", "fixed", "variable"),
        "fixed_months": 0, "margin": np.where(prod == "sme_emergency", 0.0, sb["margin"]),
        "z": sb["z"], "income": sb["turnover"] / 12 * 0.22, "other_payments": sb["existing_debt"] * 0.02,
        "fraud": False, "macro_sens": bz.SECTOR_MACRO[sb["sector_idx"].to_numpy()],
        "shock_2020": bz.SECTOR_SHOCK_2020[sb["sector_idx"].to_numpy()],
        "holiday_free": np.where(prod == "sme_emergency", 12, 0), "shadow": False,
        "secured": sb["secured"].to_numpy(), "collateral": sb["collateral_value"],
        "region": sb["region"], "channel": "branch",
    }))
    log(f"small business: {len(sa)} applications, {k} booked", t0)

    # ---------------------------------------------------------------- the engine
    A = pd.concat(accts, ignore_index=True)
    real = ~A["shadow"].to_numpy()
    counters = {p: 0 for p in PREFIX}
    ids = []
    for p, sh in zip(A["product"], A["shadow"]):
        if sh:
            ids.append(None)
        else:
            counters[p] += 1
            ids.append(f"{PREFIX[p]}{counters[p]:07d}")
    A["account_id"] = ids
    acc = engine.Accounts(
        account_id=A["account_id"].to_numpy(), product=A["product"].to_numpy(), open_t=A["open_t"].to_numpy(),
        amount=A["amount"].to_numpy(float), term=A["term"].to_numpy(int), rate=A["rate"].to_numpy(float),
        rate_type=A["rate_type"].to_numpy(), fixed_months=A["fixed_months"].to_numpy(int),
        margin=A["margin"].to_numpy(float), z=A["z"].to_numpy(float), income=A["income"].to_numpy(float),
        other_payments=A["other_payments"].to_numpy(float), fraud=A["fraud"].to_numpy(bool),
        macro_sens=A["macro_sens"].to_numpy(float), shock_2020=A["shock_2020"].to_numpy(float),
        holiday_free=A["holiday_free"].to_numpy(int), shadow=A["shadow"].to_numpy(bool), rng_seed=SEED,
        extra={"secured": A["secured"].to_numpy(bool), "collateral": A["collateral"].to_numpy(float),
               "collections_arm": np.where(rng.random(len(A)) < 0.5, "call_first", "sms_first")})
    out = engine.run(acc, macro, stress, fwd_stress, fwd_rate, rng)
    log("engine", t0)
    rec = recovery.recoveries(out["closes"], out["defaults"], acc, macro, stress, rng)
    log("recoveries", t0)

    months = out["months"]
    # Performance rows
    cols = [np.concatenate([r[j] for r in out["rows"]]) for j in range(9)]
    idx, tt = cols[0], cols[1]
    perf = pd.DataFrame({
        "account_id": acc.account_id[idx], "product": acc.product[idx], "month": months[tt],
        "balance_cents": cents(cols[2]), "limit_cents": np.where(np.isin(acc.product[idx], list(engine.REVOLVING)), cents(cols[3]), None),
        "scheduled_cents": cents(cols[4]), "paid_cents": cents(cols[5]), "missed": cols[6].astype(int),
        "payment_holiday": cols[7].astype(bool), "rate_pct": np.round(cols[8], 2), "_i": idx, "_t": tt,
    })
    perf["days_past_due"] = perf["missed"].clip(upper=12) * 30 + np.where(perf["missed"] > 12, (perf["missed"] - 12) * 30, 0)
    perf["arrears_cents"] = 0
    closes = pd.DataFrame(out["closes"], columns=["_i", "_t", "reason", "balance"])
    closes = closes[real[closes["_i"]]]
    last_status = closes.set_index(["_i", "_t"])["reason"]
    perf["status"] = np.where(perf["missed"] >= 3, "default", np.where(perf["missed"] >= 1, "arrears", "up_to_date"))
    key = pd.MultiIndex.from_arrays([perf["_i"], perf["_t"]])
    closed_reason = last_status.reindex(key).to_numpy()
    perf["status"] = np.where(pd.notna(closed_reason), closed_reason, perf["status"])
    # An account repaid or closed in full shows the payoff as paid and nothing owed.
    settled = perf["status"].isin(["repaid", "prepaid", "closed_by_customer"]).to_numpy()
    perf.loc[settled, "paid_cents"] += perf.loc[settled, "balance_cents"]
    perf.loc[settled, "balance_cents"] = 0
    # Arrears: the sum of what fell due and was not paid, over the current run of missed payments.
    perf = perf.sort_values(["_i", "_t"], kind="stable").reset_index(drop=True)
    perf["shortfall"] = (perf["scheduled_cents"] - perf["paid_cents"]).clip(lower=0)
    run_id = (perf["missed"] == 0).astype(int).groupby(perf["_i"]).cumsum()
    perf["arrears_cents"] = np.where(perf["missed"] > 0, perf.groupby([perf["_i"], run_id])["shortfall"].cumsum(), 0)
    log(f"performance: {len(perf)} rows", t0)

    # Card migration: open cards get new numbers from March 2022.
    is_card = (acc.product == "card") & real
    open_at_mig = set(perf.loc[(perf["product"] == "card") & (perf["_t"] == MIGRATION_T - 1)
                               & ~perf["status"].isin(["charged_off", "closed_by_customer"]), "_i"])
    open_at_mig &= set(perf.loc[(perf["product"] == "card") & (perf["_t"] == MIGRATION_T), "_i"])
    new_id = {}
    for j, i in enumerate(sorted(open_at_mig)):
        new_id[i] = f"CK{j + 1:07d}"
    after = perf["_i"].isin(open_at_mig) & (perf["_t"] >= MIGRATION_T)
    perf.loc[after, "account_id"] = perf.loc[after, "_i"].map(new_id)
    del is_card

    def account_at(i, t):
        return new_id[i] if (i in new_id and t >= MIGRATION_T) else acc.account_id[i]

    # ---------------------------------------------------------------- loans table
    first_t = perf.groupby("_i")["_t"].min()
    mig_limit = perf.loc[perf["_t"] == MIGRATION_T].set_index("_i")["limit_cents"]
    open_lookup = {}
    for a_ in apps:
        open_lookup.update(dict(zip(a_["app_id"], a_["open_date"])))
    open_lookup.update(dict(zip(sa["app_id"], sa["open_date"])))
    loan_rows = []
    close_map = {(i): (t, r) for i, t, r, _ in out["closes"]}
    app_index = A["app_id"].to_numpy()
    for i in np.where(real)[0]:
        if i not in first_t.index:
            continue
        p = acc.product[i]
        open_d = pd.Timestamp(months[first_t[i]]).replace(day=1).date()
        if open_lookup.get(app_index[i]) is not None:
            open_d = open_lookup[app_index[i]]
        ct = close_map.get(i)
        close_d = months[ct[0]] if ct else None
        reason = ct[1] if ct else None
        pay0 = 0.0 if p in engine.REVOLVING else float(engine.first_payment(
            acc.amount[i], acc.rate[i], acc.term[i], acc.holiday_free[i]))
        coll = A["collateral"].iat[i]
        base_row = dict(account_id=acc.account_id[i], app_id=app_index[i], product=p,
                        open_date=open_d, amount_cents=int(round(acc.amount[i] * 100)),
                        term_months=int(acc.term[i]) if p not in engine.REVOLVING else None,
                        rate_pct=round(float(acc.rate[i]), 2), rate_type=acc.rate_type[i],
                        fixed_months=int(acc.fixed_months[i]) or None,
                        payment_cents=int(round(pay0 * 100)) if pay0 else None,
                        collateral_value_cents=int(round(coll * 100)) if pd.notna(coll) else None,
                        region=A["region"].iat[i], channel=A["channel"].iat[i],
                        close_date=close_d, close_reason=reason, predecessor_id=None)
        if i in new_id:
            old = dict(base_row, close_date=months[MIGRATION_T - 1], close_reason="migrated")
            new = dict(base_row, account_id=new_id[i], open_date=dt.date(2022, 3, 1), predecessor_id=acc.account_id[i],
                       amount_cents=int(mig_limit[i]))
            loan_rows += [old, new]
        else:
            loan_rows.append(base_row)
    loans = pd.DataFrame(loan_rows)
    log(f"loans: {len(loans)}", t0)

    # ---------------------------------------------------------------- events and defaults
    ev = pd.DataFrame([(account_at(i, t), months[t], e, v) for i, t, e, v in out["events"] if real[i]],
                      columns=["account_id", "event_date", "event", "detail"])
    defaults = recorded_defaults(perf, ev, months)
    rcv = pd.DataFrame([(account_at(i, t), months[t], k, int(round(a * 100))) for i, t, k, a in rec if real[i]],
                       columns=["account_id", "month", "kind", "amount_cents"])
    log(f"defaults recorded: {len(defaults)}", t0)

    # Collections actions: what the collections team did each month an account was behind.
    beh = perf[(perf["missed"] >= 1) & (perf["status"].isin(["arrears", "default"]))]
    action = np.select([beh["missed"] == 1, beh["missed"] == 2, beh["missed"] <= 4],
                       ["reminder", "phone_call", "final_notice"], "agency_referral")
    arm = acc.extra["collections_arm"][beh["_i"].to_numpy()]
    in_test = (beh["_t"].between(96, 107)) & (beh["missed"] == 1)
    action = np.where(in_test, np.where(arm == "call_first", "phone_call", "sms"), action)
    coll = pd.DataFrame({"account_id": beh["account_id"].to_numpy(), "month": beh["month"].to_numpy(),
                         "action": action, "test_arm": np.where(in_test, arm, None)})

    # ---------------------------------------------------------------- applications tables
    capps = pd.concat(apps, ignore_index=True)
    acct_of_app = dict(zip(loans.loc[loans["predecessor_id"].isna(), "app_id"], loans.loc[loans["predecessor_id"].isna(), "account_id"]))
    capps["account_id"] = capps["app_id"].map(acct_of_app)
    verified_flag = verified(capps, rng)
    capps_out = pd.DataFrame({
        "app_id": capps["app_id"], "app_date": capps["app_date"], "product": capps["product"],
        "channel": capps["channel"], "purpose": capps["purpose"],
        "amount_requested_cents": cents(capps["amount_requested"]),
        "term_requested_months": capps["term_requested"].astype(int),
        "age": capps["age"], "region": capps["region"],
        "stated_income_cents": cents(capps["stated_income"]),
        "income_verified": verified_flag,
        # What verification found: payslips or bank statements show the true income.
        "verified_income_cents": pd.array(np.where(verified_flag, np.round(capps["true_income"].to_numpy(), -2) * 100,
                                                   None), dtype="Int64"),
        "employment": capps["employment"], "employment_months": capps["employment_months"],
        "housing": capps["housing"], "address_months": capps["address_months"], "dependants": capps["dependants"],
        "bureau_hit": capps["bureau_hit"], "bureau_score": capps["bureau_score"].astype("Int64"),
        "bureau_version": capps["bureau_version"],
        "oldest_account_months": capps["oldest_account_months"], "open_accounts": capps["open_accounts"],
        "revolving_balance_cents": cents(capps["revolving_balance"]),
        "revolving_utilisation": capps["revolving_utilisation"],
        "enquiries_6m": capps["enquiries_6m"], "worst_status_24m": capps["worst_status_24m"],
        "public_records": capps["public_records"],
        "other_payments_cents": cents(capps["other_payments"]),
        "ob_consent": capps["ob_consent"], "ob_avg_balance_cents": pd.array(np.where(capps["ob_consent"], cents(capps["ob_avg_balance"]), None), dtype="Int64"),
        "ob_overdraft_days": capps["ob_overdraft_days"].astype("Int64"),
        "ob_income_volatility": capps["ob_income_volatility"],
        "ob_returned_payments": capps["ob_returned_payments"].astype("Int64"),
        "ob_betting_share": capps["ob_betting_share"],
        "collateral_value_cents": pd.array(np.where(capps["collateral_value"].notna(), cents(capps["collateral_value"]), None), dtype="Int64"),
        "deposit_cents": cents(capps["deposit"]),
        "mark1_score": capps["mark1_score"], "cutoff": capps["cutoff"].astype(int),
        "decision": capps["decision"], "decline_reason": capps["decline_reason"], "override": capps["override"],
        "offered_rate_pct": capps["offered_rate"], "offered_amount_cents": pd.array(np.where(capps["offered_amount"].notna(), cents(capps["offered_amount"]), None), dtype="Int64"),
        "offered_term_months": np.where(capps["decision"] == "approve", capps["offered_term"], None),
        "price_test_arm": capps["price_test_arm"], "outcome": capps["outcome"], "account_id": capps["account_id"],
    })
    monitoring = pd.DataFrame({"app_id": capps["app_id"], "gender": capps["gender"]})
    sapps_out = pd.DataFrame({
        "app_id": sa["app_id"], "business_id": sa["business_id"], "app_date": sa["app_date"], "product": sa["product"],
        "sector": sa["sector"], "region": sa["region"], "legal_form": sa["legal_form"],
        "years_trading": sa["years_trading"], "turnover_cents": cents(sa["turnover"]), "owner_age": sa["owner_age"],
        "owner_bureau_score": sa["owner_bureau_score"].astype(int), "business_score": sa["business_score"].astype(int),
        "ob_avg_balance_cents": pd.array(np.where(sa["ob_avg_balance"].notna(), cents(sa["ob_avg_balance"]), None), dtype="Int64"),
        "ob_monthly_credits_cents": pd.array(np.where(sa["ob_monthly_credits"].notna(), cents(sa["ob_monthly_credits"]), None), dtype="Int64"),
        "ob_volatility": sa["ob_volatility"], "ob_overdraft_days": sa["ob_overdraft_days"].astype("Int64"),
        "ob_returned_items": sa["ob_returned_items"].astype("Int64"),
        "existing_debt_cents": cents(sa["existing_debt"]), "amount_requested_cents": cents(sa["amount_requested"]),
        "term_requested_months": sa["term_requested"].astype(int), "secured": sa["secured"],
        "collateral_value_cents": pd.array(np.where(sa["collateral_value"].notna(), cents(sa["collateral_value"]), None), dtype="Int64"),
        "guarantee": np.where(sa["product"] == "sme_emergency", "government_80pct", np.where(sa["legal_form"] == "limited", "director", "none")),
        "sme1_score": sa["sme1_score"], "cutoff": sa["cutoff"], "decision": sa["decision"],
        "decline_reason": sa["decline_reason"], "offered_rate_pct": sa["offered_rate"],
        "outcome": sa["outcome"],
    })
    sapps_out["account_id"] = sapps_out["app_id"].map(acct_of_app)
    businesses = pd.DataFrame({"business_id": biz["business_id"], "sector": biz["sector"], "legal_form": biz["legal_form"],
                               "region": biz["region"],
                               "established_year": 2016 - biz["years_trading_2016"]})

    # Bureau retro: what the bureau later saw of applicants Fernhill did not lend to.
    shadow_i = np.where(acc.shadow)[0]
    sh = pd.DataFrame({"app_id": app_index[shadow_i], "bad": out["shadow_bad"][shadow_i]})
    sh = sh.merge(capps[["app_id", "app_date", "outcome", "z"]], on="app_id")
    sh = sh[(pd.to_datetime(sh["app_date"]) >= "2019-01-01") & (pd.to_datetime(sh["app_date"]) < "2024-01-01")]
    p_open = np.where(sh["outcome"] == "not_taken_up", 0.85, ap.sigmoid(0.1 + 0.6 * sh["z"].to_numpy()))
    opened = rng.random(len(sh)) < p_open
    flip = rng.random(len(sh)) < 0.03
    retro = pd.DataFrame({"app_id": sh["app_id"], "opened_elsewhere": opened,
                          "months_to_open": np.where(opened, rng.integers(0, 7, len(sh)), None),
                          "bad_12m_elsewhere": np.where(opened, sh["bad"].to_numpy() ^ flip, None)})

    # ---------------------------------------------------------------- corporate
    corp = corporate.simulate(macro, stress, rng)
    log("corporate", t0)

    # ---------------------------------------------------------------- market and bank tables
    cof = np.round(np.maximum(policy_by_t * 0.72 + 0.55, 0.6), 2)
    rates = pd.DataFrame({"month": months, "policy_rate_pct": policy_by_t, "cost_of_funds_pct": cof,
                          "swap_2y_pct": np.round(policy_by_t + 0.15 + rng.normal(0, 0.08, 120), 2),
                          "swap_5y_pct": np.round(0.6 * policy_by_t + 1.1 + rng.normal(0, 0.1, 120), 2)})
    capital = bank_capital(perf, corp, months)

    # ---------------------------------------------------------------- truth
    pd12 = [np.concatenate([r[j] for r in out["pd12"]]) for j in range(3)]
    keep = real[pd12[0]]
    t_pd12 = pd.DataFrame({"account_id": [account_at(i, t) for i, t in zip(pd12[0][keep], pd12[1][keep])],
                           "month": months[pd12[1][keep]], "pd12": np.round(pd12[2][keep], 6)})
    first_pd = pd.DataFrame({"_i": pd12[0], "_t": pd12[1], "pd12": pd12[2]}).drop_duplicates("_i")
    orig = pd.DataFrame({"app_id": app_index[first_pd["_i"]], "pd12_at_open": np.round(first_pd["pd12"].to_numpy(), 6),
                         "shadow": acc.shadow[first_pd["_i"]],
                         "bad_12m_if_booked": np.where(acc.shadow[first_pd["_i"]], out["shadow_bad"][first_pd["_i"]], None)})
    t_app = pd.DataFrame({"app_id": capps["app_id"], "z": np.round(capps["z"], 6),
                          "true_income_cents": cents(capps["true_income"]), "fraud": capps["fraud"]})
    t_sme = pd.DataFrame({"app_id": sa["app_id"], "z": np.round(sa["z"], 6)})
    t_corp = pd.DataFrame(corp["truth"], columns=["company_id", "month", "pd_1y", "distance_to_default"])

    write(macro, scen, rates, capps_out, monitoring, sapps_out, businesses, loans, perf, ev, defaults, rcv,
          coll, retro, corp, capital, t_pd12, orig, t_app, t_sme, t_corp, t0)
    return 0


def verified(capps: pd.DataFrame, rng) -> np.ndarray:
    big = capps["amount_requested"].to_numpy() > 15000
    broker_2022 = np.isin(capps["channel"].to_numpy(), ["broker", "dealer"]) & (pd.to_datetime(capps["app_date"]) >= "2022-07-01").to_numpy()
    mortgage = capps["product"].to_numpy() == "mortgage"
    ob = capps["ob_consent"].to_numpy()
    return big | broker_2022 | mortgage | ob | (rng.random(len(capps)) < 0.1)


def recorded_defaults(perf: pd.DataFrame, ev: pd.DataFrame, months) -> pd.DataFrame:
    """Defaults as Fernhill's systems recorded them: 90 days past due until the end of
    2020, then the 2021 definition (a material 90 days past due, or bankruptcy, or
    charge-off, with three months' probation before a cure counts)."""
    p = perf[["account_id", "_t", "month", "missed", "arrears_cents", "balance_cents", "status"]].rename(columns={"_t": "t"})
    bk_rows = ev[ev["event"] == "bankruptcy"]
    bk = {}
    for a, d in zip(bk_rows["account_id"], bk_rows["event_date"]):
        bk.setdefault(a, set()).add(d)
    candidates = set(p.loc[(p["missed"] >= 3) | (p["status"] == "charged_off"), "account_id"]) | set(bk)
    p = p[p["account_id"].isin(candidates)]
    rows = []
    for acct, g in p.groupby("account_id", sort=True):
        in_def, good_run = False, 0
        bk_months = bk.get(acct, set())
        for row in g.itertuples(index=False):
            if row.t < 60:   # before January 2021: 90 days past due
                if row.missed >= 3 and not in_def:
                    rows.append([acct, row.month, "dpd90", "days_past_due", row.balance_cents, None])
                    in_def = True
                elif in_def and row.missed == 0:
                    rows[-1][5] = row.month
                    in_def = False
            else:
                material = (row.arrears_cents > 10000) and (row.arrears_cents > 0.01 * row.balance_cents)
                reason = None
                if row.missed >= 3 and material:
                    reason = "days_past_due"
                elif row.month in bk_months:
                    reason = "bankruptcy"
                elif row.status == "charged_off":
                    reason = "charged_off"
                if reason and not in_def:
                    rows.append([acct, row.month, "dod2021", reason, row.balance_cents, None])
                    in_def, good_run = True, 0
                elif in_def:
                    good_run = good_run + 1 if row.missed == 0 else 0
                    if good_run >= 3:
                        rows[-1][5] = row.month
                        in_def = False
    return pd.DataFrame(rows, columns=["account_id", "default_month", "definition", "trigger", "ead_cents", "cure_month"])


def dedupe_default_month(fm: pd.DataFrame) -> pd.DataFrame:
    """A facility's month of default has one row, the defaulted one."""
    dflt = set(zip(fm.loc[fm["status"] == "defaulted", "facility_id"], fm.loc[fm["status"] == "defaulted", "month"]))
    keep = [not (s == "performing" and (f, m) in dflt) for f, m, s in zip(fm["facility_id"], fm["month"], fm["status"])]
    return fm[keep].reset_index(drop=True)


def bank_capital(perf, corp, months) -> pd.DataFrame:
    """Fernhill's capital at each year end, set so its CET1 ratio sits where a
    mid-sized bank's does. The risk weights here are a rough standardised view; the
    book's Chapter 21 computes them properly."""
    weights = {"mortgage": 0.35, "personal": 0.75, "card": 0.75, "auto": 0.75,
               "sme_term": 0.85, "sme_overdraft": 0.85, "sme_emergency": 0.20}
    fac = pd.DataFrame(corp["facility_month"], columns=["facility_id", "month", "drawn", "limit", "status"])
    rows = []
    ratio = {2016: 0.128, 2017: 0.131, 2018: 0.133, 2019: 0.134, 2020: 0.124, 2021: 0.129,
             2022: 0.133, 2023: 0.139, 2024: 0.141, 2025: 0.142}
    for year in range(2016, 2026):
        m = dt.date(year, 12, 31)
        p = perf[perf["month"] == m]
        rwa = sum((p.loc[p["product"] == k, "balance_cents"].sum() * w) for k, w in weights.items())
        f = fac[fac["month"] == m]
        rwa += f["drawn"].sum() * 1.0 + (f["limit"] - f["drawn"]).clip(lower=0).sum() * 0.4
        credit = int(rwa)
        op = int(credit * 0.11)
        mkt = int(credit * 0.025)
        total = credit + op + mkt
        cet1 = int(total * ratio[year])
        rows.append((m, cet1, int(total * 0.015), int(total * 0.022), op, mkt))
    return pd.DataFrame(rows, columns=["year_end", "cet1_cents", "at1_cents", "tier2_cents",
                                       "operational_rwa_cents", "market_rwa_cents"])


def write(macro, scen, rates, capps, monitoring, sapps, businesses, loans, perf, ev, defaults, rcv, coll, retro,
          corp, capital, t_pd12, orig, t_app, t_sme, t_corp, t0):
    FERNHILL.mkdir(parents=True, exist_ok=True)
    for path in (LOANBOOK, TRUTH):
        if path.exists():
            path.unlink()
    con = duckdb.connect(str(LOANBOOK), config={"threads": 1})
    perf_out = perf[["account_id", "product", "month", "balance_cents", "limit_cents", "scheduled_cents",
                     "paid_cents", "arrears_cents", "missed", "days_past_due", "status",
                     "payment_holiday", "rate_pct"]].copy()
    perf_out["limit_cents"] = perf_out["limit_cents"].astype("Int64")
    perf_out = perf_out.sort_values(["account_id", "month"], kind="stable")
    tables = {
        "macro": macro, "scenarios": scen, "market_rates": rates,
        "applications": capps, "applicant_monitoring": monitoring,
        "sme_applications": sapps, "businesses": businesses,
        "accounts": loans, "performance": perf_out, "account_events": ev, "defaults": defaults,
        "recoveries": rcv.sort_values(["account_id", "month", "kind"], kind="stable"),
        "collections": coll.sort_values(["account_id", "month"], kind="stable"),
        "bureau_retro": retro,
        "companies": pd.DataFrame(corp["companies"], columns=["company_id", "name", "sector", "listed", "client_since"]),
        "financials": pd.DataFrame(corp["financials"], columns=[
            "company_id", "fiscal_year", "revenue_cents", "cogs_cents", "opex_cents", "ebitda_cents",
            "depreciation_cents", "ebit_cents", "interest_cents", "tax_cents", "net_income_cents", "cash_cents",
            "receivables_cents", "inventory_cents", "current_assets_cents", "total_assets_cents",
            "current_liabilities_cents", "total_debt_cents", "equity_cents", "capex_cents",
            "operating_cash_flow_cents", "payables_cents", "dividends_cents", "basis"]),
        "facilities": pd.DataFrame(corp["facilities"], columns=[
            "facility_id", "company_id", "kind", "start_date", "maturity_date", "limit_cents", "margin_bps",
            "secured", "seniority", "covenant_max_leverage", "covenant_min_interest_cover"]),
        "facility_months": dedupe_default_month(pd.DataFrame(corp["facility_month"],
                                               columns=["facility_id", "month", "drawn_cents", "limit_cents", "status"])),
        "ratings": pd.DataFrame(corp["ratings"], columns=["company_id", "rating_date", "internal_grade", "model_grade",
                                                          "analyst_override", "agency_rating"]),
        "market_data": pd.DataFrame(corp["market"], columns=["company_id", "month", "equity_value_cents", "equity_volatility", "cds_5y_bps"]),
        "corporate_defaults": pd.DataFrame(corp["defaults"], columns=["company_id", "default_month", "kind"]),
        "corporate_recoveries": pd.DataFrame(corp["recoveries"], columns=["facility_id", "month", "kind", "amount_cents"]),
        "credit_requests": pd.DataFrame([("R2025-117", corp["meridian_id"], dt.date(2025, 12, 15), "revolver",
                                          2_000_000_000, 36, "Working capital for growth; receivables have grown faster than sales.")],
                                        columns=["request_id", "company_id", "request_date", "facility", "amount_cents",
                                                 "tenor_months", "purpose"]),
        "bank_capital": capital,
    }
    for name, df in tables.items():
        con.register("_df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM _df")
        con.unregister("_df")
    con.close()
    tcon = duckdb.connect(str(TRUTH), config={"threads": 1})
    for name, df in {"pd12": t_pd12, "origination": orig, "applicants": t_app, "sme_applicants": t_sme,
                     "corporate_pd": t_corp}.items():
        tcon.register("_df", df)
        tcon.execute(f"CREATE TABLE {name} AS SELECT * FROM _df")
        tcon.unregister("_df")
    tcon.close()
    manifest = {name: int(len(df)) for name, df in tables.items()}
    (FERNHILL / "manifest.json").write_text(json.dumps({"seed": SEED, "tables": manifest}, indent=2) + "\n")
    log(f"written: {LOANBOOK.stat().st_size / 1e6:.0f} MB loan book, {TRUTH.stat().st_size / 1e6:.0f} MB truth", t0)


def log(msg: str, t0: float) -> None:
    print(f"  [{time.time() - t0:6.1f}s] {msg}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
