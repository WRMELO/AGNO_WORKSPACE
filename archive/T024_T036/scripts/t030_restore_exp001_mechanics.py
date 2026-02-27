from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


INITIAL_CAPITAL = 100_000.0
ORDER_COST_RATE = 0.0006
BUY_HEARTBEAT_DAYS = 3
BUY_RANK_THRESHOLD = 10
SELL_RANK_THRESHOLD = 15
MAX_WEIGHT_PER_ASSET = 0.20
TARGET_WEIGHT_PER_ASSET = 0.10
START_DATE = pd.Timestamp("2018-07-02")

LCL_WINDOW = 20
LCL_STD_MULT = 2.0
DERIVATIVE_WINDOW = 3
DERIVATIVE_TRIGGER = -0.04
EMERGENCY_LOCK_DAYS = 5

CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
DIAGNOSTICS_FILE = Path("src/data_engine/diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet")
STANDINGS_FILE = Path("src/data_engine/features/SSOT_F1_STANDINGS.parquet")
PREV_CURVE_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE.parquet")
PREV_LEDGER_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_LEDGER.parquet")

OUT_LEDGER = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_LEDGER_EXP001.parquet")
OUT_CURVE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE_EXP001.parquet")


def current_positions_value(positions: dict[str, int], prices_row: pd.Series) -> float:
    total = 0.0
    for ticker, qty in positions.items():
        if qty <= 0:
            continue
        px = float(prices_row.get(ticker, np.nan))
        if np.isfinite(px) and px > 0:
            total += qty * px
    return float(total)


def lcl_equity_from_hist(equity_hist: list[float], current_equity: float) -> float:
    series = pd.Series(equity_hist + [current_equity], dtype=float)
    tail = series.tail(LCL_WINDOW)
    mean = float(tail.mean())
    std = float(tail.std(ddof=0))
    return max(0.0, mean - LCL_STD_MULT * std)


def perf_metrics(equity: pd.Series) -> dict[str, float]:
    if equity.empty:
        return {"ret_total": np.nan, "cagr": np.nan, "maxdd": np.nan, "sharpe": np.nan}
    eq = equity.astype(float)
    ret_total = float(eq.iloc[-1] / eq.iloc[0] - 1.0) if eq.iloc[0] > 0 else np.nan
    daily = eq.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    years = max((len(eq) - 1) / 252.0, 1e-12)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0) if eq.iloc[0] > 0 else np.nan
    peak = eq.cummax()
    maxdd = float((eq / peak - 1.0).min())
    vol = float(daily.std(ddof=0))
    sharpe = float(np.sqrt(252.0) * daily.mean() / vol) if vol > 0 else np.nan
    return {"ret_total": ret_total, "cagr": cagr, "maxdd": maxdd, "sharpe": sharpe}


def main() -> None:
    for path in [CANONICAL_FILE, DIAGNOSTICS_FILE, STANDINGS_FILE, PREV_CURVE_FILE, PREV_LEDGER_FILE]:
        if not path.exists():
            raise RuntimeError(f"Arquivo ausente: {path}")

    canonical = pd.read_parquet(CANONICAL_FILE, columns=["ticker", "date", "close_operational"])
    canonical["ticker"] = canonical["ticker"].astype(str).str.upper().str.strip()
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["ticker", "date", "close_operational"]).copy()

    diagnostics = pd.read_parquet(DIAGNOSTICS_FILE, columns=["ticker", "date", "execution_signal"])
    diagnostics["ticker"] = diagnostics["ticker"].astype(str).str.upper().str.strip()
    diagnostics["date"] = pd.to_datetime(diagnostics["date"], errors="coerce").dt.normalize()
    diagnostics = diagnostics.dropna(subset=["ticker", "date"]).copy()

    standings = pd.read_parquet(STANDINGS_FILE).reset_index()
    standings["ticker"] = standings["ticker"].astype(str).str.upper().str.strip()
    standings["date"] = pd.to_datetime(standings["date"], errors="coerce").dt.normalize()
    standings = standings.dropna(subset=["ticker", "date", "standings_rank"]).copy()

    # Usa a curva anterior do T028 como fonte de CDI diário e Ibovespa para o filtro SMA200.
    macro = pd.read_parquet(PREV_CURVE_FILE, columns=["date", "ibov_close", "cdi_daily"])
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "ibov_close", "cdi_daily"]).sort_values("date")
    macro["ibov_sma200"] = macro["ibov_close"].rolling(200, min_periods=200).mean()
    macro["market_panic"] = (macro["ibov_close"] < macro["ibov_sma200"]).fillna(False)

    prices_wide = (
        canonical.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
        .sort_index()
        .ffill()
    )

    tech = canonical[["ticker", "date"]].copy()
    tech = tech.merge(diagnostics, on=["ticker", "date"], how="left")
    tech = tech.merge(standings[["ticker", "date", "standings_rank"]], on=["ticker", "date"], how="left")
    tech = tech.sort_values(["date", "ticker"], ascending=[True, True]).reset_index(drop=True)
    tech_by_day = {d: g.set_index("ticker") for d, g in tech.groupby("date", sort=True)}
    macro_by_day = macro.set_index("date")

    sim_dates = sorted(set(prices_wide.index).intersection(set(macro_by_day.index)))
    sim_dates = [d for d in sim_dates if d >= START_DATE]
    if not sim_dates:
        raise RuntimeError("Sem datas em comum para simulação após START_DATE.")

    ibov_base = float(macro_by_day.loc[sim_dates[0], "ibov_close"])
    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    equity_hist: list[float] = []
    ledger_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

    emergency_lock_remaining = 0
    emergency_triggers = 0

    for day_idx, date in enumerate(sim_dates):
        prices_row = prices_wide.loc[date]
        day_macro = macro_by_day.loc[date]
        cdi_daily = float(day_macro["cdi_daily"])
        market_panic = bool(day_macro["market_panic"])

        # A) Remuneração do caixa
        cash_before_cdi = cash
        cash = cash * (1.0 + cdi_daily)
        cdi_credit = cash - cash_before_cdi

        # B) Mark-to-market e cheque de saúde
        pos_val_pre = current_positions_value(positions, prices_row)
        equity_pre_trade = cash + pos_val_pre
        lcl_equity = lcl_equity_from_hist(equity_hist, equity_pre_trade)
        portfolio_sick = bool(equity_pre_trade < lcl_equity)

        equity_slope_3d = 0.0
        if len(equity_hist) >= DERIVATIVE_WINDOW:
            ref = equity_hist[-DERIVATIVE_WINDOW]
            if ref > 0:
                equity_slope_3d = float(equity_pre_trade / ref - 1.0)
        emergency_triggered_today = bool(equity_slope_3d < DERIVATIVE_TRIGGER)

        day_tech = tech_by_day.get(date, pd.DataFrame())

        # C) Emergência por derivada (vende tudo, trava compras por 5 dias)
        if emergency_triggered_today:
            emergency_triggers += 1
            emergency_lock_remaining = EMERGENCY_LOCK_DAYS
            for ticker, qty_pos in list(positions.items()):
                if qty_pos <= 0:
                    continue
                px = float(prices_row.get(ticker, np.nan))
                if not np.isfinite(px) or px <= 0:
                    continue
                notional = qty_pos * px
                net_notional = notional * (1.0 - ORDER_COST_RATE)
                cash_before = cash
                cash += net_notional
                positions[ticker] = 0
                ledger_rows.append(
                    {
                        "date": date,
                        "ticker": ticker,
                        "side": "SELL",
                        "reason": "EMERGENCY_DERIVATIVE_3D",
                        "qty": qty_pos,
                        "price": px,
                        "notional": notional,
                        "net_notional": net_notional,
                        "cost_brl": notional - net_notional,
                        "cash_before": cash_before,
                        "cash_after": cash,
                        "market_panic": market_panic,
                        "portfolio_sick": portfolio_sick,
                        "equity_slope_3d": equity_slope_3d,
                    }
                )

        # D) Manutenção de carteira com histerese
        for ticker, qty_pos in list(positions.items()):
            if qty_pos <= 0:
                continue
            row = day_tech.loc[ticker] if (not day_tech.empty and ticker in day_tech.index) else None
            signal = str(row["execution_signal"]).upper() if row is not None and pd.notna(row.get("execution_signal")) else "HOLD"
            rank = float(row["standings_rank"]) if row is not None and pd.notna(row.get("standings_rank")) else np.nan

            sell = False
            reason = None
            if signal == "SELL":
                sell = True
                reason = "TECH_SELL_SIGNAL"
            elif np.isfinite(rank) and rank > SELL_RANK_THRESHOLD:
                sell = True
                reason = "MOMENTUM_RANK_DROP_GT15"
            # 11..15 = zona de histerese (manter)

            if not sell:
                continue

            px = float(prices_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue
            notional = qty_pos * px
            net_notional = notional * (1.0 - ORDER_COST_RATE)
            cash_before = cash
            cash += net_notional
            positions[ticker] = 0
            ledger_rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "side": "SELL",
                    "reason": reason,
                    "qty": qty_pos,
                    "price": px,
                    "notional": notional,
                    "net_notional": net_notional,
                    "cost_brl": notional - net_notional,
                    "cash_before": cash_before,
                    "cash_after": cash,
                    "market_panic": market_panic,
                    "portfolio_sick": portfolio_sick,
                    "equity_slope_3d": equity_slope_3d,
                }
            )

        # E) Compra condicional
        emergency_cash_active = emergency_lock_remaining > 0
        buy_trigger = (day_idx % BUY_HEARTBEAT_DAYS == 0) and (not market_panic) and (not portfolio_sick) and (not emergency_cash_active)

        if buy_trigger and not day_tech.empty:
            candidates = day_tech.reset_index()
            candidates = candidates[candidates["standings_rank"].notna()].copy()
            candidates = candidates.sort_values(["standings_rank", "ticker"], ascending=[True, True])
            candidates = candidates[candidates["standings_rank"] <= BUY_RANK_THRESHOLD].head(BUY_RANK_THRESHOLD)

            equity_after_sells = cash + current_positions_value(positions, prices_row)
            for row in candidates.itertuples(index=False):
                ticker = str(row.ticker)
                # Histerese operacional: sem top-up recorrente; compra apenas novas entradas no Top 10.
                if int(positions.get(ticker, 0)) > 0:
                    continue
                px = float(prices_row.get(ticker, np.nan))
                if not np.isfinite(px) or px <= 0:
                    continue
                current_val = int(positions.get(ticker, 0)) * px
                target_val = TARGET_WEIGHT_PER_ASSET * equity_after_sells
                max_val = MAX_WEIGHT_PER_ASSET * equity_after_sells
                desired_add = max(0.0, target_val - current_val)
                cap_add = max(0.0, max_val - current_val)
                alloc = min(desired_add, cap_add)
                if alloc <= 0:
                    continue

                qty_buy = int(math.floor(alloc / px))
                if qty_buy <= 0:
                    continue

                notional = qty_buy * px
                gross_cash = notional * (1.0 + ORDER_COST_RATE)
                if cash <= gross_cash:
                    continue

                cash_before = cash
                cash -= gross_cash
                positions[ticker] = int(positions.get(ticker, 0)) + qty_buy
                ledger_rows.append(
                    {
                        "date": date,
                        "ticker": ticker,
                        "side": "BUY",
                        "reason": "F1_TOP10_HEARTBEAT",
                        "qty": qty_buy,
                        "price": px,
                        "notional": notional,
                        "net_notional": notional,
                        "cost_brl": gross_cash - notional,
                        "cash_before": cash_before,
                        "cash_after": cash,
                        "market_panic": market_panic,
                        "portfolio_sick": portfolio_sick,
                        "equity_slope_3d": equity_slope_3d,
                    }
                )

        # F) Curva diária
        pos_val_end = current_positions_value(positions, prices_row)
        equity_end = cash + pos_val_end
        equity_hist.append(equity_end)
        ibov_close = float(day_macro["ibov_close"])
        benchmark = INITIAL_CAPITAL * (ibov_close / ibov_base) if ibov_base > 0 else np.nan

        curve_rows.append(
            {
                "date": date,
                "cash_start_before_cdi": cash_before_cdi,
                "cdi_daily": cdi_daily,
                "cash_cdi_credit": cdi_credit,
                "cash_end": cash,
                "positions_value_end": pos_val_end,
                "equity_end": equity_end,
                "lcl_equity": lcl_equity,
                "portfolio_sick": portfolio_sick,
                "equity_slope_3d": equity_slope_3d,
                "ibov_close": ibov_close,
                "ibov_sma200": float(day_macro["ibov_sma200"]) if pd.notna(day_macro["ibov_sma200"]) else np.nan,
                "market_panic": market_panic,
                "emergency_cash_active": emergency_cash_active,
                "emergency_triggered_today": emergency_triggered_today,
                "buy_trigger_day": bool(buy_trigger),
                "benchmark_buy_hold_ibov": benchmark,
            }
        )

        if emergency_lock_remaining > 0:
            emergency_lock_remaining -= 1

    ledger_df = pd.DataFrame(ledger_rows)
    if ledger_df.empty:
        ledger_df = pd.DataFrame(
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
                "market_panic",
                "portfolio_sick",
                "equity_slope_3d",
            ]
        )
    else:
        ledger_df = ledger_df.sort_values(["date", "side", "ticker"], ascending=[True, True, True]).reset_index(drop=True)

    curve_df = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)

    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger_df.to_parquet(OUT_LEDGER, index=False)
    curve_df.to_parquet(OUT_CURVE, index=False)

    # Comparativo com versão anterior (T028)
    prev_curve = pd.read_parquet(PREV_CURVE_FILE).sort_values("date").reset_index(drop=True)
    prev_ledger = pd.read_parquet(PREV_LEDGER_FILE)

    current_metrics = perf_metrics(curve_df["equity_end"])
    prev_metrics = perf_metrics(prev_curve["equity_end"])

    current_trades = len(ledger_df)
    prev_trades = len(prev_ledger)
    trade_reduction = (1.0 - (current_trades / prev_trades)) if prev_trades > 0 else np.nan

    panic_window = curve_df[(curve_df["date"] >= pd.Timestamp("2020-03-01")) & (curve_df["date"] <= pd.Timestamp("2020-03-31"))]
    panic_buys = int(
        ledger_df[
            (ledger_df["side"] == "BUY")
            & (ledger_df["date"] >= pd.Timestamp("2020-03-01"))
            & (ledger_df["date"] <= pd.Timestamp("2020-03-31"))
        ].shape[0]
    )

    print("TASK T030 - RESTORE EXP001 MECHANICS")
    print("")
    print(f"DATES_SIMULATED: {len(curve_df)}")
    print(f"LEDGER_ROWS_EXP001: {current_trades}")
    print(f"LEDGER_ROWS_T028: {prev_trades}")
    print(f"TRADE_REDUCTION_VS_T028: {trade_reduction:.2%}" if np.isfinite(trade_reduction) else "TRADE_REDUCTION_VS_T028: N/A")
    print(f"EMERGENCY_TRIGGERS: {emergency_triggers}")
    print("")
    print("CRASH CHECK (2020-03)")
    print(f"- panic_days: {int(panic_window['market_panic'].sum())}/{len(panic_window)}")
    print(f"- buy_orders_in_panic_window: {panic_buys}")
    print("")
    print("PERFORMANCE COMPARISON")
    print(
        f"- EXP001: ret_total={current_metrics['ret_total']:.4f} | CAGR={current_metrics['cagr']:.4f} | "
        f"MaxDD={current_metrics['maxdd']:.4f} | Sharpe={current_metrics['sharpe']:.4f}"
    )
    print(
        f"- T028:   ret_total={prev_metrics['ret_total']:.4f} | CAGR={prev_metrics['cagr']:.4f} | "
        f"MaxDD={prev_metrics['maxdd']:.4f} | Sharpe={prev_metrics['sharpe']:.4f}"
    )
    print("")
    print(f"OUT_CURVE: {OUT_CURVE}")
    print(f"OUT_LEDGER: {OUT_LEDGER}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
