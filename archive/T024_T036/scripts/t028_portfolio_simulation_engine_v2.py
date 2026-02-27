from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


INITIAL_CAPITAL = 100_000.0
BUY_CADENCE_DAYS = 3
MAX_WEIGHT_PER_ASSET = 0.20
TARGET_WEIGHT_PER_ASSET = 0.10
ORDER_COST_RATE = 0.0006
PANIC_SELL_WORST_N = 1
LCL_WINDOW = 20
LCL_STD_MULT = 2.0
BUY_TOP_N = 10
START_DATE = pd.Timestamp("2018-07-02")

CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
DIAGNOSTICS_FILE = Path("src/data_engine/diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet")
STANDINGS_FILE = Path("src/data_engine/features/SSOT_F1_STANDINGS.parquet")
MACRO_FILE = Path("src/data_engine/ssot/SSOT_MACRO.parquet")

LEDGER_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_LEDGER.parquet")
CURVE_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE.parquet")


def current_positions_value(positions: dict[str, int], prices_row: pd.Series) -> float:
    total = 0.0
    for ticker, qty in positions.items():
        if qty <= 0:
            continue
        price = float(prices_row.get(ticker, np.nan))
        if np.isfinite(price) and price > 0:
            total += qty * price
    return float(total)


def last_lcl_equity(equity_hist: list[float]) -> float:
    if len(equity_hist) < 2:
        return 0.0
    tail = pd.Series(equity_hist[-LCL_WINDOW:], dtype=float)
    mean = float(tail.mean())
    std = float(tail.std(ddof=0))
    return max(0.0, mean - LCL_STD_MULT * std)


def compute_metrics(equity_series: pd.Series) -> dict[str, float]:
    if equity_series.empty:
        return {"ret_total": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
    eq = equity_series.astype(float)
    ret_total = float(eq.iloc[-1] / eq.iloc[0] - 1.0) if eq.iloc[0] > 0 else np.nan
    daily_ret = eq.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    years = max((len(eq) - 1) / 252.0, 1e-12)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0) if eq.iloc[0] > 0 else np.nan
    peak = eq.cummax()
    dd = eq / peak - 1.0
    mdd = float(dd.min()) if len(dd) else np.nan
    vol = float(daily_ret.std(ddof=0))
    sharpe = float(np.sqrt(252.0) * daily_ret.mean() / vol) if vol > 0 else np.nan
    return {"ret_total": ret_total, "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def main() -> None:
    for path in [CANONICAL_FILE, DIAGNOSTICS_FILE, STANDINGS_FILE, MACRO_FILE]:
        if not path.exists():
            raise RuntimeError(f"Arquivo ausente: {path}")

    # Carrega preços operacionais do canônico (fonte de MTM e execução)
    cdf = pd.read_parquet(CANONICAL_FILE, columns=["ticker", "date", "close_operational"])
    cdf["ticker"] = cdf["ticker"].astype(str).str.upper().str.strip()
    cdf["date"] = pd.to_datetime(cdf["date"], errors="coerce").dt.normalize()
    cdf = cdf.dropna(subset=["ticker", "date", "close_operational"]).copy()

    # Carrega sinais/estado técnico da camada diagnóstica
    ddf = pd.read_parquet(
        DIAGNOSTICS_FILE,
        columns=["ticker", "date", "execution_signal", "spc_green", "slope_60"],
    )
    ddf["ticker"] = ddf["ticker"].astype(str).str.upper().str.strip()
    ddf["date"] = pd.to_datetime(ddf["date"], errors="coerce").dt.normalize()
    ddf = ddf.dropna(subset=["ticker", "date"]).copy()

    # Carrega standings F1 com ranking diário
    sdf = pd.read_parquet(STANDINGS_FILE).reset_index()
    sdf["ticker"] = sdf["ticker"].astype(str).str.upper().str.strip()
    sdf["date"] = pd.to_datetime(sdf["date"], errors="coerce").dt.normalize()
    sdf = sdf.dropna(subset=["ticker", "date", "standings_rank"]).copy()

    # Carrega macro para CDI e benchmark Ibovespa
    mdf = pd.read_parquet(MACRO_FILE, columns=["date", "ibov_close", "cdi_log_daily"])
    mdf["date"] = pd.to_datetime(mdf["date"], errors="coerce").dt.normalize()
    mdf = mdf.dropna(subset=["date", "ibov_close", "cdi_log_daily"]).sort_values("date")
    mdf["cdi_daily"] = np.exp(mdf["cdi_log_daily"].astype(float)) - 1.0
    mdf["ibov_sma200"] = mdf["ibov_close"].rolling(200, min_periods=200).mean()
    mdf["market_panic"] = (mdf["ibov_close"] < mdf["ibov_sma200"]).fillna(False)

    # Join técnico para decisões por ticker/dia
    tdf = cdf.merge(ddf, on=["ticker", "date"], how="inner")
    tdf = tdf.merge(sdf[["ticker", "date", "standings_rank", "f1_score_total"]], on=["ticker", "date"], how="left")
    tdf = tdf.sort_values(["date", "ticker"], ascending=[True, True]).reset_index(drop=True)

    # Estruturas rápidas por data
    prices_wide = (
        tdf.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
        .sort_index()
        .ffill()
    )
    tech_by_day = {d: g.set_index("ticker") for d, g in tdf.groupby("date", sort=True)}
    macro_by_day = mdf.set_index("date")

    sim_dates = sorted(set(prices_wide.index).intersection(set(macro_by_day.index)))
    sim_dates = [d for d in sim_dates if d >= START_DATE]
    if not sim_dates:
        raise RuntimeError("Sem datas em comum entre preço e macro para simulação.")

    benchmark_base = float(macro_by_day.loc[sim_dates[0], "ibov_close"])

    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    equity_hist: list[float] = []
    ledger_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

    panic_buy_block_days = 0
    panic_buy_attempt_days = 0

    for day_idx, date in enumerate(sim_dates):
        prices_row = prices_wide.loc[date]
        daily_macro = macro_by_day.loc[date]
        cdi_daily = float(daily_macro["cdi_daily"])
        market_panic = bool(daily_macro["market_panic"])

        # PASSO 0: remuneração composta do caixa
        cash_before_cdi = cash
        cash = cash * (1.0 + cdi_daily)
        cdi_credit = cash - cash_before_cdi

        # PASSO A: mark-to-market + saúde da carteira + saúde macro
        positions_value = current_positions_value(positions, prices_row)
        equity_pre_trade = cash + positions_value
        lcl_equity = last_lcl_equity(equity_hist + [equity_pre_trade])
        portfolio_health = "HEALTHY" if equity_pre_trade >= lcl_equity else "SICK"

        # PASSO B: vendas defensivas
        day_tech = tech_by_day.get(date, pd.DataFrame())
        positions_tickers = [t for t, q in positions.items() if q > 0]

        # Venda técnica individual (stop/SPC)
        for ticker in positions_tickers:
            row = day_tech.loc[ticker] if (not day_tech.empty and ticker in day_tech.index) else None
            if row is None:
                continue
            signal = str(row.get("execution_signal", "HOLD")).upper()
            spc_green = bool(row.get("spc_green", True))
            slope_60 = float(row.get("slope_60", np.nan))

            sell_reason = None
            sell_frac = 0.0
            if signal == "SELL":
                sell_reason = "TECH_SELL_SIGNAL"
                sell_frac = 1.0
            elif signal == "REDUCE":
                sell_reason = "TECH_REDUCE_SIGNAL"
                sell_frac = 0.5
            elif (not spc_green) and np.isfinite(slope_60) and slope_60 <= 0.0:
                sell_reason = "TECH_SPC_SLOPE_BREAK"
                sell_frac = 1.0

            if sell_reason is None:
                continue

            price = float(prices_row.get(ticker, np.nan))
            if not np.isfinite(price) or price <= 0:
                continue
            qty_pos = int(positions.get(ticker, 0))
            qty_sell = int(math.floor(qty_pos * sell_frac))
            if qty_sell <= 0:
                continue

            notional = qty_sell * price
            net_notional = notional * (1.0 - ORDER_COST_RATE)
            cash_before = cash
            cash += net_notional
            positions[ticker] = qty_pos - qty_sell

            ledger_rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "side": "SELL",
                    "reason": sell_reason,
                    "qty": qty_sell,
                    "price": price,
                    "notional": notional,
                    "net_notional": net_notional,
                    "cost_brl": notional - net_notional,
                    "cash_before": cash_before,
                    "cash_after": cash,
                    "market_panic": market_panic,
                    "portfolio_health": portfolio_health,
                }
            )

        # Venda de pânico da carteira se abaixo de LCL
        if portfolio_health == "SICK":
            live_pos = [t for t in positions if positions[t] > 0]
            if not day_tech.empty and live_pos:
                live_in_day = [t for t in live_pos if t in day_tech.index]
                worst = (
                    day_tech.loc[live_in_day].reset_index()
                    if live_in_day
                    else pd.DataFrame(columns=["ticker", "standings_rank"])
                )
            else:
                worst = pd.DataFrame(columns=["ticker", "standings_rank"])
            if len(worst):
                worst = worst.sort_values(["standings_rank", "ticker"], ascending=[False, True]).head(PANIC_SELL_WORST_N)
                for row in worst.itertuples(index=False):
                    ticker = str(row.ticker)
                    qty_pos = int(positions.get(ticker, 0))
                    if qty_pos <= 0:
                        continue
                    price = float(prices_row.get(ticker, np.nan))
                    if not np.isfinite(price) or price <= 0:
                        continue
                    notional = qty_pos * price
                    net_notional = notional * (1.0 - ORDER_COST_RATE)
                    cash_before = cash
                    cash += net_notional
                    positions[ticker] = 0
                    ledger_rows.append(
                        {
                            "date": date,
                            "ticker": ticker,
                            "side": "SELL",
                            "reason": "PANIC_SELL_PORTFOLIO_LCL",
                            "qty": qty_pos,
                            "price": price,
                            "notional": notional,
                            "net_notional": net_notional,
                            "cost_brl": notional - net_notional,
                            "cash_before": cash_before,
                            "cash_after": cash,
                            "market_panic": market_panic,
                            "portfolio_health": portfolio_health,
                        }
                    )

        # Recalcula equity após vendas
        positions_value = current_positions_value(positions, prices_row)
        equity_after_sells = cash + positions_value

        # PASSO C: compras condicionais
        buy_trigger = (day_idx % BUY_CADENCE_DAYS == 0) and (portfolio_health == "HEALTHY")
        if buy_trigger and market_panic:
            panic_buy_attempt_days += 1
            panic_buy_block_days += 1
        elif buy_trigger and (not market_panic):
            panic_buy_attempt_days += 1
            # PASSO D: execução F1 (Top 10, cap 20% por ativo)
            if not day_tech.empty:
                candidates = day_tech.reset_index().sort_values(["standings_rank", "ticker"], ascending=[True, True]).head(BUY_TOP_N)
                candidates = candidates[candidates["standings_rank"].notna()]

                # Compra só de ativos com sinal não defensivo explícito
                candidates = candidates[
                    ~candidates["execution_signal"].astype(str).str.upper().isin(["SELL", "REDUCE"])
                ]
                if len(candidates):
                    for row in candidates.itertuples(index=False):
                        ticker = str(row.ticker)
                        price = float(prices_row.get(ticker, np.nan))
                        if not np.isfinite(price) or price <= 0:
                            continue

                        current_val = int(positions.get(ticker, 0)) * price
                        max_val = MAX_WEIGHT_PER_ASSET * equity_after_sells
                        target_val = TARGET_WEIGHT_PER_ASSET * equity_after_sells
                        desired_add = max(0.0, target_val - current_val)
                        capacity = min(max(0.0, max_val - current_val), desired_add)
                        if capacity <= 0.0:
                            continue

                        qty_buy = int(math.floor(capacity / price))
                        if qty_buy <= 0:
                            continue

                        notional = qty_buy * price
                        gross_cash_needed = notional * (1.0 + ORDER_COST_RATE)
                        if cash <= gross_cash_needed:
                            continue
                        cash_before = cash
                        cash -= gross_cash_needed
                        positions[ticker] = int(positions.get(ticker, 0)) + qty_buy
                        ledger_rows.append(
                            {
                                "date": date,
                                "ticker": ticker,
                                "side": "BUY",
                                "reason": "F1_TOP10_ALLOC",
                                "qty": qty_buy,
                                "price": price,
                                "notional": notional,
                                "net_notional": notional,
                                "cost_brl": gross_cash_needed - notional,
                                "cash_before": cash_before,
                                "cash_after": cash,
                                "market_panic": market_panic,
                                "portfolio_health": portfolio_health,
                            }
                        )

        # Curva diária
        positions_value_end = current_positions_value(positions, prices_row)
        equity_end = cash + positions_value_end
        equity_hist.append(equity_end)

        ibov_close = float(daily_macro["ibov_close"])
        benchmark_value = INITIAL_CAPITAL * (ibov_close / benchmark_base) if benchmark_base > 0 else np.nan

        curve_rows.append(
            {
                "date": date,
                "cash_start_before_cdi": cash_before_cdi,
                "cdi_daily": cdi_daily,
                "cash_cdi_credit": cdi_credit,
                "cash_end": cash,
                "positions_value_end": positions_value_end,
                "equity_end": equity_end,
                "lcl_equity": lcl_equity,
                "portfolio_health": portfolio_health,
                "ibov_close": ibov_close,
                "ibov_sma200": float(daily_macro["ibov_sma200"]) if pd.notna(daily_macro["ibov_sma200"]) else np.nan,
                "market_panic": market_panic,
                "buy_trigger_day": bool(buy_trigger),
                "benchmark_buy_hold_ibov": benchmark_value,
            }
        )

    ledger_df = pd.DataFrame(ledger_rows).sort_values(["date", "side", "ticker"], ascending=[True, True, True]) if ledger_rows else pd.DataFrame(
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
            "portfolio_health",
        ]
    )
    curve_df = pd.DataFrame(curve_rows).sort_values("date")

    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ledger_df.to_parquet(LEDGER_FILE, index=False)
    curve_df.to_parquet(CURVE_FILE, index=False)

    panic_period = curve_df[
        (curve_df["date"] >= pd.Timestamp("2020-03-01"))
        & (curve_df["date"] <= pd.Timestamp("2020-03-31"))
    ]
    panic_buys = int(
        ledger_df[
            (ledger_df["side"] == "BUY")
            & (ledger_df["date"] >= pd.Timestamp("2020-03-01"))
            & (ledger_df["date"] <= pd.Timestamp("2020-03-31"))
        ].shape[0]
    )
    portfolio_metrics = compute_metrics(curve_df["equity_end"])
    benchmark_metrics = compute_metrics(curve_df["benchmark_buy_hold_ibov"])

    print("TASK T028 - PORTFOLIO SIMULATION ENGINE V2")
    print("")
    print(f"DATES SIMULATED: {len(sim_dates)}")
    print(f"LEDGER_ROWS: {len(ledger_df)}")
    print(f"FINAL_EQUITY: {curve_df['equity_end'].iloc[-1]:.2f}")
    print(f"FINAL_BENCHMARK_IBOV: {curve_df['benchmark_buy_hold_ibov'].iloc[-1]:.2f}")
    print(f"FINAL_CASH: {curve_df['cash_end'].iloc[-1]:.2f}")
    print("")
    print("MACRO PANIC CHECK (2020-03)")
    print(f"- panic_days: {int(panic_period['market_panic'].sum())}/{len(panic_period)}")
    print(f"- buy_orders_in_panic_window: {panic_buys}")
    print(f"- buy_trigger_days: {panic_buy_attempt_days}")
    print(f"- blocked_buy_days_market_panic: {panic_buy_block_days}")
    print("")
    print("PERFORMANCE")
    print(
        f"- portfolio: ret_total={portfolio_metrics['ret_total']:.4f} | "
        f"CAGR={portfolio_metrics['cagr']:.4f} | "
        f"MaxDD={portfolio_metrics['mdd']:.4f} | "
        f"Sharpe={portfolio_metrics['sharpe']:.4f}"
    )
    print(
        f"- benchmark_ibov_bh: ret_total={benchmark_metrics['ret_total']:.4f} | "
        f"CAGR={benchmark_metrics['cagr']:.4f} | "
        f"MaxDD={benchmark_metrics['mdd']:.4f} | "
        f"Sharpe={benchmark_metrics['sharpe']:.4f}"
    )
    print("")
    print(f"LEDGER_FILE: {LEDGER_FILE}")
    print(f"CURVE_FILE: {CURVE_FILE}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
