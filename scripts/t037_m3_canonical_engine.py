from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


INITIAL_CAPITAL = 100_000.0
ORDER_COST_RATE = 0.00025
BUY_CADENCE_DAYS = 3
TOP_N = 10
LOOKBACK = 62
TARGET_PCT = 0.10
MAX_PCT = 0.15
START_DATE = pd.Timestamp("2018-07-02")

CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
MACRO_FILE = Path("src/data_engine/ssot/SSOT_MACRO.parquet")
BLACKLIST_FILE = Path("src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json")

OUT_SCORES = Path("src/data_engine/features/T037_M3_SCORES_DAILY.parquet")
OUT_LEDGER = Path("src/data_engine/portfolio/T037_PORTFOLIO_LEDGER.parquet")
OUT_CURVE = Path("src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet")
OUT_SUMMARY = Path("src/data_engine/portfolio/T037_BASELINE_SUMMARY.json")


def load_blacklist() -> set[str]:
    bl = json.load(open(BLACKLIST_FILE))
    return set(bl["tickers_list"])


def zscore_cross_section(values: pd.Series) -> pd.Series:
    x = values.astype(float)
    mu = x.mean()
    sd = x.std(ddof=0)
    if not np.isfinite(sd) or sd <= 0:
        return pd.Series(np.zeros(len(x), dtype=float), index=x.index)
    return (x - mu) / sd


def positions_value(positions: dict[str, int], px_row: pd.Series) -> float:
    total = 0.0
    for ticker, qty in positions.items():
        if qty <= 0:
            continue
        px = float(px_row.get(ticker, np.nan))
        if np.isfinite(px) and px > 0:
            total += qty * px
    return float(total)


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    return float(dd.min())


def compute_metrics(equity: pd.Series) -> dict[str, float]:
    if equity.empty or equity.iloc[0] <= 0:
        return {"ret_total": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
    eq = equity.astype(float)
    ret_total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    daily = eq.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    years = max((len(eq) - 1) / 252.0, 1e-12)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = max_drawdown(eq)
    vol = float(daily.std(ddof=0))
    sharpe = float(np.sqrt(252.0) * daily.mean() / vol) if vol > 0 else np.nan
    return {"ret_total": ret_total, "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


# ── PHASE 1: M3 SCORES ──────────────────────────────────────────────

def compute_m3_scores(
    canonical: pd.DataFrame, blacklist: set[str]
) -> pd.DataFrame:
    df = canonical[~canonical["ticker"].isin(blacklist)].copy()
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    px_wide = (
        df.pivot_table(
            index="date", columns="ticker",
            values="close_operational", aggfunc="first",
        )
        .sort_index()
        .ffill()
    )

    logret = np.log(px_wide / px_wide.shift(1))

    score_m0 = logret.rolling(window=LOOKBACK, min_periods=LOOKBACK).mean()
    ret_62 = logret.rolling(window=LOOKBACK, min_periods=LOOKBACK).sum()
    vol_62 = logret.rolling(window=LOOKBACK, min_periods=LOOKBACK).std(ddof=0)

    records: list[dict] = []
    dates = sorted(px_wide.index)

    for d in dates:
        m0_row = score_m0.loc[d].dropna()
        r_row = ret_62.loc[d].dropna()
        v_row = vol_62.loc[d].dropna()

        common = m0_row.index.intersection(r_row.index).intersection(v_row.index)
        if len(common) < 3:
            continue

        cs = pd.DataFrame({
            "score_m0": m0_row[common],
            "ret_62": r_row[common],
            "vol_62": v_row[common],
        })

        cs["z_m0"] = zscore_cross_section(cs["score_m0"])
        cs["z_ret"] = zscore_cross_section(cs["ret_62"])
        cs["z_vol"] = zscore_cross_section(cs["vol_62"])
        cs["score_m3"] = cs["z_m0"] + cs["z_ret"] - cs["z_vol"]

        cs = cs.sort_values("score_m3", ascending=False).reset_index()
        cs["m3_rank"] = range(1, len(cs) + 1)
        cs["date"] = d

        for row in cs.itertuples(index=False):
            records.append({
                "date": d,
                "ticker": row.ticker,
                "score_m0": row.score_m0,
                "ret_62": row.ret_62,
                "vol_62": row.vol_62,
                "z_m0": row.z_m0,
                "z_ret": row.z_ret,
                "z_vol": row.z_vol,
                "score_m3": row.score_m3,
                "m3_rank": row.m3_rank,
            })

    scores_df = pd.DataFrame(records)
    return scores_df


# ── PHASE 2: BURNER STRESS ──────────────────────────────────────────

def compute_burner_stress(
    canonical: pd.DataFrame, blacklist: set[str]
) -> dict[tuple[str, pd.Timestamp], bool]:
    df = canonical[~canonical["ticker"].isin(blacklist)].copy()

    stress_i = (
        df["i_value"].notna()
        & df["i_lcl"].notna()
        & (df["i_value"] < df["i_lcl"])
    )
    stress_amp = (
        df["mr_value"].notna()
        & df["mr_ucl"].notna()
        & (df["mr_value"] > df["mr_ucl"])
    )
    df["burner_stress"] = stress_i | stress_amp

    df["burner_stress_exec"] = (
        df.groupby("ticker", sort=False)["burner_stress"]
        .shift(1)
        .fillna(False)
    )

    stress_map: dict[tuple[str, pd.Timestamp], bool] = {}
    for row in df[["ticker", "date", "burner_stress_exec"]].itertuples(index=False):
        stress_map[(row.ticker, row.date)] = bool(row.burner_stress_exec)

    return stress_map


# ── PHASE 3: PORTFOLIO SIMULATION ───────────────────────────────────

def run_simulation(
    scores_df: pd.DataFrame,
    stress_map: dict[tuple[str, pd.Timestamp], bool],
    canonical: pd.DataFrame,
    macro: pd.DataFrame,
    blacklist: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:

    prices = canonical[~canonical["ticker"].isin(blacklist)].copy()
    px_wide = (
        prices.pivot_table(
            index="date", columns="ticker",
            values="close_operational", aggfunc="first",
        )
        .sort_index()
        .ffill()
    )

    macro_day = macro.set_index("date")

    scores_by_day: dict[pd.Timestamp, pd.DataFrame] = {}
    for d, g in scores_df.groupby("date", sort=True):
        scores_by_day[d] = g.set_index("ticker")

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [d for d in sim_dates if d >= START_DATE]
    if not sim_dates:
        raise RuntimeError("Sem datas em comum para simulação.")

    ibov_base = float(macro_day.loc[sim_dates[0], "ibov_close"])

    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    ledger_rows: list[dict] = []
    curve_rows: list[dict] = []

    for day_idx, d in enumerate(sim_dates):
        px_row = px_wide.loc[d]
        m = macro_day.loc[d]
        cdi_log = float(m["cdi_log_daily"]) if pd.notna(m["cdi_log_daily"]) else 0.0
        cdi_daily = np.exp(cdi_log) - 1.0
        ibov = float(m["ibov_close"])

        cash_before_cdi = cash
        cash *= (1.0 + cdi_daily)
        cdi_credit = cash - cash_before_cdi

        pos_val_pre = positions_value(positions, px_row)
        equity_pre = cash + pos_val_pre

        # ── SELLS: burner stress ──
        for ticker, qty in list(positions.items()):
            if qty <= 0:
                continue
            is_stressed = stress_map.get((ticker, d), False)
            if not is_stressed:
                continue

            px = float(px_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue

            notional = qty * px
            net = notional * (1.0 - ORDER_COST_RATE)
            cash_before = cash
            cash += net
            positions[ticker] = 0

            ledger_rows.append({
                "date": d, "ticker": ticker, "side": "SELL",
                "reason": "BURNER_STRESS_CEP",
                "qty": qty, "price": px,
                "notional": notional, "net_notional": net,
                "cost_brl": notional - net,
                "cash_before": cash_before, "cash_after": cash,
            })

        # ── Recalc after sells ──
        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # ── SELL: trim positions above MAX_PCT ──
        for ticker, qty in list(positions.items()):
            if qty <= 0:
                continue
            px = float(px_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue
            cur_val = qty * px
            cur_pct = cur_val / equity_mid if equity_mid > 0 else 0.0
            if cur_pct <= MAX_PCT:
                continue
            target_val = TARGET_PCT * equity_mid
            excess_val = max(0.0, cur_val - target_val)
            qty_sell = int(min(qty, math.floor(excess_val / px)))
            if qty_sell <= 0:
                continue
            notional = qty_sell * px
            net = notional * (1.0 - ORDER_COST_RATE)
            cash_before = cash
            cash += net
            positions[ticker] = qty - qty_sell
            ledger_rows.append({
                "date": d, "ticker": ticker, "side": "SELL",
                "reason": "TRIM_TO_TARGET",
                "qty": qty_sell, "price": px,
                "notional": notional, "net_notional": net,
                "cost_brl": notional - net,
                "cash_before": cash_before, "cash_after": cash,
            })

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # ── BUYS: top 10 M3, cadence 3d, no stress ──
        buy_day = (day_idx % BUY_CADENCE_DAYS == 0)

        if buy_day and d in scores_by_day:
            day_scores = scores_by_day[d]
            top_candidates = day_scores[day_scores["m3_rank"] <= TOP_N].copy()
            top_candidates = top_candidates.sort_values("m3_rank")

            for row in top_candidates.itertuples():
                ticker = str(row.Index)

                is_stressed = stress_map.get((ticker, d), False)
                if is_stressed:
                    continue

                px = float(px_row.get(ticker, np.nan))
                if not np.isfinite(px) or px <= 0:
                    continue

                cur_qty = int(positions.get(ticker, 0))
                cur_val = cur_qty * px
                target_val = TARGET_PCT * equity_mid
                need_val = max(0.0, target_val - cur_val)
                if need_val <= 0:
                    continue

                qty_buy = int(math.floor(need_val / px))
                if qty_buy <= 0:
                    continue

                notional = qty_buy * px
                gross = notional * (1.0 + ORDER_COST_RATE)
                if cash <= gross:
                    continue

                cash_before = cash
                cash -= gross
                positions[ticker] = cur_qty + qty_buy

                ledger_rows.append({
                    "date": d, "ticker": ticker, "side": "BUY",
                    "reason": "M3_TOP10_RECOMPOSE",
                    "qty": qty_buy, "price": px,
                    "notional": notional, "net_notional": notional,
                    "cost_brl": gross - notional,
                    "cash_before": cash_before, "cash_after": cash,
                })

                pos_val_mid = positions_value(positions, px_row)
                equity_mid = cash + pos_val_mid

        # ── DAILY CURVE ──
        pos_val_end = positions_value(positions, px_row)
        equity_end = cash + pos_val_end
        exposure = pos_val_end / equity_end if equity_end > 0 else 0.0
        benchmark = INITIAL_CAPITAL * (ibov / ibov_base) if ibov_base > 0 else np.nan

        n_positions = sum(1 for q in positions.values() if q > 0)

        curve_rows.append({
            "date": d,
            "cash_end": cash,
            "positions_value_end": pos_val_end,
            "equity_end": equity_end,
            "exposure": exposure,
            "n_positions": n_positions,
            "cdi_daily": cdi_daily,
            "cdi_credit": cdi_credit,
            "ibov_close": ibov,
            "benchmark_ibov": benchmark,
        })

    ledger = pd.DataFrame(ledger_rows)
    if ledger.empty:
        ledger = pd.DataFrame(columns=[
            "date", "ticker", "side", "reason", "qty", "price",
            "notional", "net_notional", "cost_brl",
            "cash_before", "cash_after",
        ])
    else:
        ledger = ledger.sort_values(["date", "side", "ticker"]).reset_index(drop=True)

    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
    return ledger, curve


# ── MAIN ─────────────────────────────────────────────────────────────

def main() -> None:
    for path in [CANONICAL_FILE, MACRO_FILE, BLACKLIST_FILE]:
        if not path.exists():
            raise RuntimeError(f"Arquivo ausente: {path}")

    blacklist = load_blacklist()

    canonical = pd.read_parquet(CANONICAL_FILE)
    canonical["ticker"] = canonical["ticker"].astype(str).str.upper().str.strip()
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["ticker", "date", "close_operational"]).copy()

    macro = pd.read_parquet(MACRO_FILE)
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "ibov_close", "cdi_log_daily"]).sort_values("date")

    print("TASK T037 — M3 CANONICAL ENGINE")
    print(f"BASELINE: score_m3 = z(score_m0) + z(ret_62) - z(vol_62)")
    print(f"BLACKLIST: {len(blacklist)} tickers excluidos")
    print(f"COST: {ORDER_COST_RATE:.4%} por trade")
    print(f"CANONICAL: {canonical['ticker'].nunique()} tickers, {len(canonical):,} linhas")
    print()

    print("PHASE 1: Computing M3 scores...")
    scores_df = compute_m3_scores(canonical, blacklist)
    n_score_dates = scores_df["date"].nunique()
    print(f"  M3 scores: {len(scores_df):,} ticker-days, {n_score_dates} dates")

    print("PHASE 2: Computing burner stress signals...")
    stress_map = compute_burner_stress(canonical, blacklist)
    n_stressed = sum(1 for v in stress_map.values() if v)
    print(f"  Stress signals (exec D+1): {n_stressed:,} ticker-days stressed")

    print("PHASE 3: Running portfolio simulation...")
    ledger, curve = run_simulation(scores_df, stress_map, canonical, macro, blacklist)

    for p in [OUT_SCORES, OUT_LEDGER, OUT_CURVE]:
        p.parent.mkdir(parents=True, exist_ok=True)
    scores_df.to_parquet(OUT_SCORES, index=False)
    ledger.to_parquet(OUT_LEDGER, index=False)
    curve.to_parquet(OUT_CURVE, index=False)

    # ── PHASE 4: VALIDATION ──
    print()
    print("PHASE 4: Validation")

    portfolio_m = compute_metrics(curve["equity_end"])
    benchmark_m = compute_metrics(curve["benchmark_ibov"])

    n_buys = int((ledger["side"] == "BUY").sum()) if not ledger.empty else 0
    n_sells = int((ledger["side"] == "SELL").sum()) if not ledger.empty else 0
    n_stress_sells = int((ledger["reason"] == "BURNER_STRESS_CEP").sum()) if not ledger.empty else 0
    total_cost = float(ledger["cost_brl"].sum()) if not ledger.empty else 0.0

    cdi_wealth = (1.0 + curve["cdi_daily"]).cumprod()
    cdi_final = float(INITIAL_CAPITAL * cdi_wealth.iloc[-1] / cdi_wealth.iloc[0])
    macro_aligned = macro[macro["date"].isin(curve["date"])].sort_values("date")
    cdi_growth_simple = float((1.0 + curve["cdi_daily"].astype(float)).iloc[1:].prod() - 1.0)
    cdi_growth_log = float(np.expm1(macro_aligned["cdi_log_daily"].astype(float).iloc[1:].sum()))
    cdi_rel_err = abs(cdi_growth_simple - cdi_growth_log) / max(1e-12, abs(cdi_growth_log))

    panic_window = curve[
        (curve["date"] >= pd.Timestamp("2020-03-01"))
        & (curve["date"] <= pd.Timestamp("2020-03-31"))
    ]
    panic_buys = 0
    if not ledger.empty:
        panic_buys = int(ledger[
            (ledger["side"] == "BUY")
            & (ledger["date"] >= pd.Timestamp("2020-03-01"))
            & (ledger["date"] <= pd.Timestamp("2020-03-31"))
        ].shape[0])

    summary = {
        "task_id": "T037",
        "equity_final": float(curve["equity_end"].iloc[-1]),
        "cagr": float(portfolio_m["cagr"]),
        "mdd": float(portfolio_m["mdd"]),
        "sharpe": float(portfolio_m["sharpe"]),
        "n_buys": n_buys,
        "n_sells": n_sells,
        "n_stress_sells": n_stress_sells,
        "total_cost": total_cost,
        "avg_exposure": float(curve["exposure"].mean()),
        "avg_positions": float(curve["n_positions"].mean()),
        "benchmark_ibov_final": float(curve["benchmark_ibov"].iloc[-1]),
        "cdi_final": cdi_final,
        "dates_simulated": int(len(curve)),
        "panic_buys_mar2020": panic_buys,
        "shapes": {
            "scores_rows": int(len(scores_df)),
            "ledger_rows": int(len(ledger)),
            "curve_rows": int(len(curve)),
        },
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=True, indent=2)
        f.write("\n")

    print(f"  DATES_SIMULATED: {len(curve)}")
    print(f"  FINAL_EQUITY: R$ {curve['equity_end'].iloc[-1]:,.2f}")
    print(f"  FINAL_BENCHMARK_IBOV: R$ {curve['benchmark_ibov'].iloc[-1]:,.2f}")
    print(f"  FINAL_CDI_ACUM: R$ {cdi_final:,.2f}")
    print(f"  CDI_GROWTH_SIMPLE: {cdi_growth_simple:.6f}")
    print(f"  CDI_GROWTH_LOGSUM: {cdi_growth_log:.6f}")
    print(f"  CDI_GROWTH_REL_ERR: {cdi_rel_err:.12f}")
    print(f"  TRADES: {n_buys} BUY + {n_sells} SELL = {n_buys + n_sells} total")
    print(f"  STRESS_SELLS: {n_stress_sells}")
    print(f"  TOTAL_COST: R$ {total_cost:,.2f}")
    print(f"  AVG_EXPOSURE: {curve['exposure'].mean():.4f}")
    print(f"  AVG_POSITIONS: {curve['n_positions'].mean():.1f}")
    print()
    print("PERFORMANCE")
    print(
        f"  Portfolio: ret={portfolio_m['ret_total']:.4f} | "
        f"CAGR={portfolio_m['cagr']:.4f} | "
        f"MDD={portfolio_m['mdd']:.4f} | "
        f"Sharpe={portfolio_m['sharpe']:.4f}"
    )
    print(
        f"  Ibov B&H: ret={benchmark_m['ret_total']:.4f} | "
        f"CAGR={benchmark_m['cagr']:.4f} | "
        f"MDD={benchmark_m['mdd']:.4f} | "
        f"Sharpe={benchmark_m['sharpe']:.4f}"
    )
    print()
    print(f"COVID CHECK (Mar/2020): buys_in_panic={panic_buys}")
    print()
    print(f"OUT_SCORES: {OUT_SCORES}")
    print(f"OUT_LEDGER: {OUT_LEDGER}")
    print(f"OUT_CURVE: {OUT_CURVE}")
    print(f"OUT_SUMMARY: {OUT_SUMMARY}")
    print()

    if cdi_rel_err > 1e-6:
        raise RuntimeError(
            f"CDI sanity failed: rel_err={cdi_rel_err:.12f} exceeds 1e-6."
        )

    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
