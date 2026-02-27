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
TARGET_PCT = 0.10
MAX_PCT = 0.15
START_DATE = pd.Timestamp("2018-07-02")

SLOPE_WINDOW = 4
HYSTERESIS_ENTER = 2
HYSTERESIS_EXIT = 3

CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
MACRO_FILE = Path("src/data_engine/ssot/SSOT_MACRO.parquet")
BLACKLIST_FILE = Path("src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json")
SCORES_FILE = Path("src/data_engine/features/T037_M3_SCORES_DAILY.parquet")
T037_SUMMARY_FILE = Path("src/data_engine/portfolio/T037_BASELINE_SUMMARY.json")

OUT_LEDGER = Path("src/data_engine/portfolio/T038_PORTFOLIO_LEDGER.parquet")
OUT_CURVE = Path("src/data_engine/portfolio/T038_PORTFOLIO_CURVE.parquet")
OUT_SUMMARY = Path("src/data_engine/portfolio/T038_BASELINE_SUMMARY.json")


def load_blacklist() -> set[str]:
    with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
        bl = json.load(f)
    return set(bl["tickers_list"])


def positions_value(positions: dict[str, int], px_row: pd.Series) -> float:
    total = 0.0
    for ticker, qty in positions.items():
        if qty <= 0:
            continue
        px = float(px_row.get(ticker, np.nan))
        if np.isfinite(px) and px > 0:
            total += qty * px
    return float(total)


def compute_metrics(equity: pd.Series) -> dict[str, float]:
    if equity.empty or equity.iloc[0] <= 0:
        return {"ret_total": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
    eq = equity.astype(float)
    ret_total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    daily = eq.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    years = max((len(eq) - 1) / 252.0, 1e-12)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    roll_max = eq.cummax()
    mdd = float((eq / roll_max - 1.0).min())
    vol = float(daily.std(ddof=0))
    sharpe = float(np.sqrt(252.0) * daily.mean() / vol) if vol > 0 else np.nan
    return {"ret_total": ret_total, "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def rolling_slope(series: pd.Series, window: int) -> pd.Series:
    y = series.astype(float)
    out = np.full(len(y), np.nan, dtype=float)
    if window < 2:
        return pd.Series(out, index=y.index)

    x = np.arange(window, dtype=float)
    x_center = x - x.mean()
    denom = float(np.sum(x_center ** 2))
    if denom <= 0:
        return pd.Series(out, index=y.index)

    arr = y.to_numpy()
    for i in range(window - 1, len(arr)):
        wv = arr[i - window + 1 : i + 1]
        if not np.all(np.isfinite(wv)):
            continue
        y_center = wv - np.mean(wv)
        out[i] = float(np.sum(x_center * y_center) / denom)
    return pd.Series(out, index=y.index)


def run_simulation(
    scores_df: pd.DataFrame,
    canonical: pd.DataFrame,
    macro: pd.DataFrame,
    blacklist: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    prices = canonical[~canonical["ticker"].isin(blacklist)].copy()
    px_wide = (
        prices.pivot_table(
            index="date",
            columns="ticker",
            values="close_operational",
            aggfunc="first",
        )
        .sort_index()
        .ffill()
    )
    logret_wide = np.log(px_wide / px_wide.shift(1))

    # Reusa os sinais de stress do T037 (D+1).
    stress_i = (
        prices["i_value"].notna()
        & prices["i_lcl"].notna()
        & (prices["i_value"] < prices["i_lcl"])
    )
    stress_amp = (
        prices["mr_value"].notna()
        & prices["mr_ucl"].notna()
        & (prices["mr_value"] > prices["mr_ucl"])
    )
    prices["burner_stress_exec"] = (
        (stress_i | stress_amp).groupby(prices["ticker"], sort=False).shift(1).fillna(False)
    )
    stress_map = {
        (r.ticker, r.date): bool(r.burner_stress_exec)
        for r in prices[["ticker", "date", "burner_stress_exec"]].itertuples(index=False)
    }

    macro_day = macro.set_index("date")
    scores_by_day: dict[pd.Timestamp, pd.DataFrame] = {}
    for d, g in scores_df.groupby("date", sort=True):
        scores_by_day[d] = g.set_index("ticker")

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [d for d in sim_dates if d >= START_DATE]
    if not sim_dates:
        raise RuntimeError("Sem datas em comum para simulacao.")

    ibov_base = float(macro_day.loc[sim_dates[0], "ibov_close"])

    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    ledger_rows: list[dict] = []
    curve_rows: list[dict] = []

    regime_defensivo = False
    regime_history: list[bool] = []
    portfolio_logret_hist: list[float] = []
    num_switches = 0
    blocked_buy_events = 0

    for day_idx, d in enumerate(sim_dates):
        px_row = px_wide.loc[d]
        m = macro_day.loc[d]
        cdi_log = float(m["cdi_log_daily"]) if pd.notna(m["cdi_log_daily"]) else 0.0
        cdi_daily = np.exp(cdi_log) - 1.0
        ibov = float(m["ibov_close"])

        cash_before_cdi = cash
        cash *= (1.0 + cdi_daily)
        cdi_credit = cash - cash_before_cdi

        # SELLS: burner stress (igual T037)
        for ticker, qty in list(positions.items()):
            if qty <= 0:
                continue
            if not stress_map.get((ticker, d), False):
                continue
            px = float(px_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue
            notional = qty * px
            net = notional * (1.0 - ORDER_COST_RATE)
            cash_before = cash
            cash += net
            positions[ticker] = 0
            ledger_rows.append(
                {
                    "date": d,
                    "ticker": ticker,
                    "side": "SELL",
                    "reason": "BURNER_STRESS_CEP",
                    "qty": qty,
                    "price": px,
                    "notional": notional,
                    "net_notional": net,
                    "cost_brl": notional - net,
                    "cash_before": cash_before,
                    "cash_after": cash,
                }
            )

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # SELL trim acima de MAX_PCT (igual T037)
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
            ledger_rows.append(
                {
                    "date": d,
                    "ticker": ticker,
                    "side": "SELL",
                    "reason": "TRIM_TO_TARGET",
                    "qty": qty_sell,
                    "price": px,
                    "notional": notional,
                    "net_notional": net,
                    "cost_brl": notional - net,
                    "cash_before": cash_before,
                    "cash_after": cash,
                }
            )

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # BUYS: bloqueia em defensivo; fora disso, igual T037.
        buy_day = day_idx % BUY_CADENCE_DAYS == 0
        if buy_day and d in scores_by_day and not regime_defensivo:
            day_scores = scores_by_day[d]
            top_candidates = day_scores[day_scores["m3_rank"] <= TOP_N].sort_values("m3_rank")
            for row in top_candidates.itertuples():
                ticker = str(row.Index)
                if stress_map.get((ticker, d), False):
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
                ledger_rows.append(
                    {
                        "date": d,
                        "ticker": ticker,
                        "side": "BUY",
                        "reason": "M3_TOP10_RECOMPOSE",
                        "qty": qty_buy,
                        "price": px,
                        "notional": notional,
                        "net_notional": notional,
                        "cost_brl": gross - notional,
                        "cash_before": cash_before,
                        "cash_after": cash,
                    }
                )
                pos_val_mid = positions_value(positions, px_row)
                equity_mid = cash + pos_val_mid
        elif buy_day and d in scores_by_day and regime_defensivo:
            blocked_buy_events += 1

        # Curva diária e logret da carteira em carteira.
        pos_val_end = positions_value(positions, px_row)
        equity_end = cash + pos_val_end
        exposure = pos_val_end / equity_end if equity_end > 0 else 0.0
        benchmark = INITIAL_CAPITAL * (ibov / ibov_base) if ibov_base > 0 else np.nan
        n_positions = sum(1 for q in positions.values() if q > 0)

        held = [t for t, q in positions.items() if q > 0 and t in logret_wide.columns]
        if held:
            lr = logret_wide.loc[d, held]
            lr = lr[np.isfinite(lr)]
            portfolio_logret = float(lr.mean()) if len(lr) > 0 else 0.0
        else:
            portfolio_logret = 0.0
        portfolio_logret_hist.append(portfolio_logret)

        slope_today = float("nan")
        slopes = rolling_slope(pd.Series(portfolio_logret_hist, dtype=float), SLOPE_WINDOW)
        if len(slopes) > 0 and np.isfinite(slopes.iloc[-1]):
            slope_today = float(slopes.iloc[-1])

        prev_state = regime_defensivo
        if np.isfinite(slope_today) and len(slopes) >= HYSTERESIS_ENTER:
            s0 = float(slopes.iloc[-1]) if np.isfinite(slopes.iloc[-1]) else np.nan
            s1 = float(slopes.iloc[-2]) if np.isfinite(slopes.iloc[-2]) else np.nan
            enter = np.isfinite(s0) and np.isfinite(s1) and s0 < 0.0 and s1 < 0.0

            exit_cond = False
            if len(slopes) >= HYSTERESIS_EXIT:
                s2 = float(slopes.iloc[-3]) if np.isfinite(slopes.iloc[-3]) else np.nan
                exit_cond = (
                    np.isfinite(s0)
                    and np.isfinite(s1)
                    and np.isfinite(s2)
                    and s0 > 0.0
                    and s1 > 0.0
                    and s2 > 0.0
                )

            if not regime_defensivo and enter:
                regime_defensivo = True
            elif regime_defensivo and exit_cond:
                regime_defensivo = False

        if regime_defensivo != prev_state:
            num_switches += 1

        regime_history.append(regime_defensivo)
        curve_rows.append(
            {
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
                "regime_defensivo": regime_defensivo,
                "slope_daily": slope_today,
                "num_switches_cumsum": num_switches,
            }
        )

    ledger = pd.DataFrame(ledger_rows)
    if ledger.empty:
        ledger = pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "side",
                "reason",
                "qty",
                "price",
                "notional",
                "net_notional",
                "cost_brl",
                "cash_before",
                "cash_after",
            ]
        )
    else:
        ledger = ledger.sort_values(["date", "side", "ticker"]).reset_index(drop=True)

    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
    extra = {"num_switches": num_switches, "blocked_buy_events": blocked_buy_events}
    return ledger, curve, extra


def main() -> None:
    for p in [CANONICAL_FILE, MACRO_FILE, BLACKLIST_FILE, SCORES_FILE, T037_SUMMARY_FILE]:
        if not p.exists():
            raise RuntimeError(f"Arquivo ausente: {p}")

    blacklist = load_blacklist()

    canonical = pd.read_parquet(CANONICAL_FILE)
    canonical["ticker"] = canonical["ticker"].astype(str).str.upper().str.strip()
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["ticker", "date", "close_operational"]).copy()

    macro = pd.read_parquet(MACRO_FILE)
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "ibov_close", "cdi_log_daily"]).sort_values("date")

    scores_df = pd.read_parquet(SCORES_FILE)
    scores_df["date"] = pd.to_datetime(scores_df["date"], errors="coerce").dt.normalize()

    with open(T037_SUMMARY_FILE, "r", encoding="utf-8") as f:
        t037 = json.load(f)

    print("TASK T038 — MASTER GATE (REGIME DA CARTEIRA)")
    print(f"PARAMS: slope_window={SLOPE_WINDOW}, hysteresis={HYSTERESIS_ENTER}-in/{HYSTERESIS_EXIT}-out")
    print(f"BLACKLIST: {len(blacklist)} tickers excluidos")
    print()

    ledger, curve, extra = run_simulation(scores_df, canonical, macro, blacklist)

    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    curve.to_parquet(OUT_CURVE, index=False)
    ledger.to_parquet(OUT_LEDGER, index=False)

    portfolio_m = compute_metrics(curve["equity_end"])
    n_buys = int((ledger["side"] == "BUY").sum()) if not ledger.empty else 0
    n_sells = int((ledger["side"] == "SELL").sum()) if not ledger.empty else 0
    n_stress_sells = int((ledger["reason"] == "BURNER_STRESS_CEP").sum()) if not ledger.empty else 0
    total_cost = float(ledger["cost_brl"].sum()) if not ledger.empty else 0.0
    cdi_wealth = (1.0 + curve["cdi_daily"]).cumprod()
    cdi_final = float(INITIAL_CAPITAL * cdi_wealth.iloc[-1] / cdi_wealth.iloc[0]) if len(cdi_wealth) > 0 else np.nan
    macro_aligned = macro[macro["date"].isin(curve["date"])].sort_values("date")
    cdi_growth_simple = (
        float((1.0 + curve["cdi_daily"].astype(float)).iloc[1:].prod() - 1.0) if len(cdi_wealth) > 1 else np.nan
    )
    cdi_growth_log = (
        float(np.expm1(macro_aligned["cdi_log_daily"].astype(float).iloc[1:].sum())) if len(macro_aligned) > 1 else np.nan
    )
    cdi_rel_err = (
        abs(cdi_growth_simple - cdi_growth_log) / max(1e-12, abs(cdi_growth_log))
        if np.isfinite(cdi_growth_simple) and np.isfinite(cdi_growth_log)
        else np.nan
    )
    days_defensive_pct = float(curve["regime_defensivo"].mean()) if len(curve) > 0 else 0.0
    num_switches = int(extra["num_switches"])

    panic_mask = (
        (pd.to_datetime(ledger["date"]) >= pd.Timestamp("2020-03-01"))
        & (pd.to_datetime(ledger["date"]) <= pd.Timestamp("2020-03-31"))
        & (ledger["side"] == "BUY")
    )
    panic_buys = int(ledger.loc[panic_mask].shape[0]) if not ledger.empty else 0

    summary = {
        "task_id": "T038",
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
        "num_switches": num_switches,
        "days_defensive_pct": days_defensive_pct,
        "blocked_buy_events": int(extra["blocked_buy_events"]),
        "t037_baseline": t037,
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=True, indent=2)
        f.write("\n")

    print("COMPARISON T037 vs T038")
    print(f"  panic_buys_mar2020: {t037['panic_buys_mar2020']} -> {summary['panic_buys_mar2020']}")
    print(f"  mdd: {t037['mdd']:.4f} -> {summary['mdd']:.4f}")
    print(f"  cagr: {t037['cagr']:.4f} -> {summary['cagr']:.4f}")
    print(f"  sharpe: {t037['sharpe']:.4f} -> {summary['sharpe']:.4f}")
    print(f"  cdi_growth_simple: {cdi_growth_simple:.6f}")
    print(f"  cdi_growth_logsum: {cdi_growth_log:.6f}")
    print(f"  cdi_growth_rel_err: {cdi_rel_err:.12f}")
    print(f"  num_switches: {summary['num_switches']}")
    print(f"  days_defensive_pct: {summary['days_defensive_pct']:.4f}")
    print(f"  blocked_buy_events: {summary['blocked_buy_events']}")

    # Gate lógico obrigatório da T038.
    if summary["panic_buys_mar2020"] >= t037["panic_buys_mar2020"]:
        raise RuntimeError("Master Gate nao reduziu panic_buys_mar2020 vs T037.")
    if not np.isfinite(cdi_rel_err) or cdi_rel_err > 1e-6:
        raise RuntimeError(f"CDI sanity failed: rel_err={cdi_rel_err} exceeds 1e-6.")

    print()
    print(f"OUT_LEDGER: {OUT_LEDGER}")
    print(f"OUT_CURVE: {OUT_CURVE}")
    print(f"OUT_SUMMARY: {OUT_SUMMARY}")
    print()
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
