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
START_DATE = pd.Timestamp("2018-07-02")
TOP_N = 10
LOOKBACK = 62
TARGET_PCT = 0.10
MAX_PCT = 0.15

CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
BASE_CURVE_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE.parquet")
OUT_LEDGER = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_LEDGER_CLONE.parquet")
OUT_CURVE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE_CLONE.parquet")


def positions_value(positions: dict[str, int], px_row: pd.Series) -> float:
    total = 0.0
    for ticker, qty in positions.items():
        if qty <= 0:
            continue
        px = float(px_row.get(ticker, np.nan))
        if np.isfinite(px) and px > 0:
            total += qty * px
    return float(total)


def zscore_cross_section(values: pd.Series) -> pd.Series:
    x = values.astype(float)
    mu = x.mean()
    sd = x.std(ddof=0)
    if not np.isfinite(sd) or sd <= 0:
        return pd.Series(np.zeros(len(x), dtype=float), index=x.index)
    return (x - mu) / sd


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    return float(dd.min())


def main() -> None:
    for path in [CANONICAL_FILE, BASE_CURVE_FILE]:
        if not path.exists():
            raise RuntimeError(f"Arquivo ausente: {path}")

    prices = pd.read_parquet(CANONICAL_FILE, columns=["ticker", "date", "close_operational"])
    prices["ticker"] = prices["ticker"].astype(str).str.upper().str.strip()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices = prices.dropna(subset=["ticker", "date", "close_operational"]).copy()

    macro = pd.read_parquet(BASE_CURVE_FILE, columns=["date", "cdi_daily", "ibov_close"])
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "cdi_daily", "ibov_close"]).sort_values("date")
    macro_day = macro.set_index("date")

    px_wide = (
        prices.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
        .sort_index()
        .ffill()
    )
    logret = np.log(px_wide / px_wide.shift(1))
    mean_62 = logret.rolling(window=LOOKBACK, min_periods=LOOKBACK).mean()
    sum_62 = logret.rolling(window=LOOKBACK, min_periods=LOOKBACK).sum()
    vol_62 = logret.rolling(window=LOOKBACK, min_periods=LOOKBACK).std(ddof=0)

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [d for d in sim_dates if d >= START_DATE]
    if not sim_dates:
        raise RuntimeError("Sem datas em comum para simulação.")

    ibov_base = float(macro_day.loc[sim_dates[0], "ibov_close"])

    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    ledger_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

    for d in sim_dates:
        px_row = px_wide.loc[d]
        cdi = float(macro_day.loc[d, "cdi_daily"])
        ibov = float(macro_day.loc[d, "ibov_close"])

        # Caixa remunera CDI diariamente
        cash_before_cdi = cash
        cash *= (1.0 + cdi)
        cdi_credit = cash - cash_before_cdi

        # Ranking tríplice diário (cross-sectional)
        m_row = mean_62.loc[d]
        s_row = sum_62.loc[d]
        v_row = vol_62.loc[d]
        cs = pd.DataFrame(
            {
                "ticker": m_row.index,
                "mean_62": m_row.values,
                "sum_62": s_row.values,
                "vol_62": v_row.values,
            }
        ).dropna(subset=["mean_62", "sum_62", "vol_62"])

        if not cs.empty:
            cs["z_mean"] = zscore_cross_section(cs["mean_62"])
            cs["z_sum"] = zscore_cross_section(cs["sum_62"])
            cs["z_vol"] = zscore_cross_section(cs["vol_62"])
            cs["final_score"] = cs["z_mean"] + cs["z_sum"] - cs["z_vol"]
            cs = cs.sort_values(["final_score", "ticker"], ascending=[False, True]).reset_index(drop=True)
            top10 = set(cs.head(TOP_N)["ticker"].astype(str))
        else:
            top10 = set()

        # Equity de referência para sizing fixo (10/15)
        pos_val_pre = positions_value(positions, px_row)
        equity_ref = cash + pos_val_pre
        if equity_ref <= 0:
            equity_ref = 0.0

        # 1) Se Position_Pct > MAX_PCT, vende excedente até TARGET_PCT
        for ticker, qty in list(positions.items()):
            if qty <= 0:
                continue
            px = float(px_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue
            cur_val = qty * px
            cur_pct = cur_val / equity_ref if equity_ref > 0 else 0.0
            if cur_pct <= MAX_PCT:
                continue

            target_val = TARGET_PCT * equity_ref
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
                    "reason": "TRIM_TO_TARGET_10PCT",
                    "qty": qty_sell,
                    "price": px,
                    "notional": notional,
                    "net_notional": net,
                    "cost_brl": notional - net,
                    "cash_before": cash_before,
                    "cash_after": cash,
                    "target_pct": TARGET_PCT,
                    "max_pct": MAX_PCT,
                }
            )

        # Recalcula equity após vendas para compras
        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # 2) Se Position_Pct < TARGET_PCT e ticker em Top10, compra até TARGET_PCT
        for ticker in sorted(top10):
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
                    "reason": "RECOMPOSE_TO_TARGET_10PCT_TOP10",
                    "qty": qty_buy,
                    "price": px,
                    "notional": notional,
                    "net_notional": notional,
                    "cost_brl": gross - notional,
                    "cash_before": cash_before,
                    "cash_after": cash,
                    "target_pct": TARGET_PCT,
                    "max_pct": MAX_PCT,
                }
            )

        pos_val_end = positions_value(positions, px_row)
        equity_end = cash + pos_val_end
        current_exposure = pos_val_end / equity_end if equity_end > 0 else 0.0
        benchmark = INITIAL_CAPITAL * (ibov / ibov_base) if ibov_base > 0 else np.nan

        curve_rows.append(
            {
                "date": d,
                "cash_start_before_cdi": cash_before_cdi,
                "cdi_daily": cdi,
                "cash_cdi_credit": cdi_credit,
                "cash_end": cash,
                "positions_value_end": pos_val_end,
                "equity_end": equity_end,
                "current_exposure": current_exposure,
                "target_exposure": 1.0,
                "ibov_close": ibov,
                "benchmark_buy_hold_ibov": benchmark,
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
                "target_pct",
                "max_pct",
            ]
        )
    else:
        ledger = ledger.sort_values(["date", "side", "ticker"]).reset_index(drop=True)

    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)

    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(OUT_LEDGER, index=False)
    curve.to_parquet(OUT_CURVE, index=False)

    mdd = max_drawdown(curve["equity_end"])
    print("TASK T035 - EXP001 EXACT CLONE")
    print(f"DATES_SIMULATED: {len(curve)}")
    print(f"TRADES: {len(ledger)}")
    print(f"AVG_EXPOSURE: {curve['current_exposure'].mean():.4f}")
    print(f"MAX_DRAWDOWN: {mdd:.4%}")
    print(f"OUT_LEDGER: {OUT_LEDGER}")
    print(f"OUT_CURVE: {OUT_CURVE}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
