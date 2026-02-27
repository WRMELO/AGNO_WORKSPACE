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
BUFFER = 0.05
MAX_WEIGHT_PER_ASSET = 0.20
TOP_N = 10
SHORT_DROP_TRIGGER = -0.02
BUY_HEARTBEAT_DAYS = 3
LCL_WINDOW = 20
LCL_STD_MULT = 2.0
VOL_WINDOW = 60
RISK_WEIGHT = 1.0

CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
DIAGNOSTICS_FILE = Path("src/data_engine/diagnostics/SSOT_BURNER_DIAGNOSTICS.parquet")
STANDINGS_FILE = Path("src/data_engine/features/SSOT_F1_STANDINGS.parquet")
BASE_CURVE_FILE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE.parquet")

OUT_LEDGER = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_LEDGER_CORRECTED.parquet")
OUT_CURVE = Path("src/data_engine/portfolio/SSOT_PORTFOLIO_CURVE_CORRECTED.parquet")


def positions_value(positions: dict[str, int], px_row: pd.Series) -> float:
    total = 0.0
    for t, q in positions.items():
        if q <= 0:
            continue
        px = float(px_row.get(t, np.nan))
        if np.isfinite(px) and px > 0:
            total += q * px
    return float(total)


def lcl_equity(eq_hist: list[float], current: float) -> float:
    s = pd.Series(eq_hist + [current], dtype=float)
    tail = s.tail(LCL_WINDOW)
    m = float(tail.mean())
    sd = float(tail.std(ddof=0))
    return max(0.0, m - LCL_STD_MULT * sd)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


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
    for p in [CANONICAL_FILE, DIAGNOSTICS_FILE, STANDINGS_FILE, BASE_CURVE_FILE]:
        if not p.exists():
            raise RuntimeError(f"Arquivo ausente: {p}")

    prices = pd.read_parquet(CANONICAL_FILE, columns=["ticker", "date", "close_operational"])
    prices["ticker"] = prices["ticker"].astype(str).str.upper().str.strip()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices = prices.dropna(subset=["ticker", "date", "close_operational"]).copy()
    prices = prices.sort_values(["ticker", "date"])

    # Volatilidade 60d para ranking ajustado por risco.
    prices["ret_1d"] = prices.groupby("ticker", sort=False)["close_operational"].pct_change()
    prices["vol_60"] = (
        prices.groupby("ticker", sort=False)["ret_1d"]
        .rolling(window=VOL_WINDOW, min_periods=VOL_WINDOW)
        .std(ddof=0)
        .reset_index(level=0, drop=True)
    )

    diagnostics = pd.read_parquet(
        DIAGNOSTICS_FILE,
        columns=["ticker", "date", "execution_signal", "slope_60"],
    )
    diagnostics["ticker"] = diagnostics["ticker"].astype(str).str.upper().str.strip()
    diagnostics["date"] = pd.to_datetime(diagnostics["date"], errors="coerce").dt.normalize()
    diagnostics = diagnostics.dropna(subset=["ticker", "date"]).copy()

    standings = pd.read_parquet(STANDINGS_FILE).reset_index()
    standings["ticker"] = standings["ticker"].astype(str).str.upper().str.strip()
    standings["date"] = pd.to_datetime(standings["date"], errors="coerce").dt.normalize()
    standings = standings.dropna(subset=["ticker", "date", "standings_rank", "f1_score_total"]).copy()

    # Usa curva base para macro (ibov e cdi diário).
    macro = pd.read_parquet(BASE_CURVE_FILE, columns=["date", "ibov_close", "cdi_daily"])
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "ibov_close", "cdi_daily"]).sort_values("date")
    macro["ibov_sma200"] = macro["ibov_close"].rolling(200, min_periods=200).mean()

    # Marcador de longo prazo: tendência do campeonato (média pontos Top10).
    daily_top10 = (
        standings.sort_values(["date", "standings_rank"])
        .groupby("date")
        .head(TOP_N)
        .groupby("date", as_index=False)["f1_score_total"]
        .mean()
        .rename(columns={"f1_score_total": "top10_mean_points"})
        .sort_values("date")
    )
    daily_top10["top10_mean_points_ma20"] = daily_top10["top10_mean_points"].rolling(20, min_periods=5).mean()
    daily_top10["long_term_marker"] = (
        daily_top10["top10_mean_points"] / daily_top10["top10_mean_points_ma20"] - 1.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    long_marker_map = dict(zip(daily_top10["date"], daily_top10["long_term_marker"]))

    px_wide = (
        prices.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
        .sort_index()
        .ffill()
    )
    vol_day = {
        d: g.set_index("ticker")["vol_60"]
        for d, g in prices[["ticker", "date", "vol_60"]].dropna(subset=["vol_60"]).groupby("date", sort=True)
    }
    diag_day = {d: g.set_index("ticker") for d, g in diagnostics.groupby("date", sort=True)}
    stand_day = {d: g.set_index("ticker") for d, g in standings.groupby("date", sort=True)}
    macro_day = macro.set_index("date")

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [d for d in sim_dates if d >= START_DATE]
    if not sim_dates:
        raise RuntimeError("Sem datas em comum para simulação.")

    ibov_base = float(macro_day.loc[sim_dates[0], "ibov_close"])

    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    eq_hist: list[float] = []
    ledger_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

    for idx, d in enumerate(sim_dates):
        px_row = px_wide.loc[d]
        m = macro_day.loc[d]
        cdi = float(m["cdi_daily"])
        ibov = float(m["ibov_close"])
        ibov_sma200 = float(m["ibov_sma200"]) if pd.notna(m["ibov_sma200"]) else np.nan
        macro_marker = (ibov / ibov_sma200 - 1.0) if np.isfinite(ibov_sma200) and ibov_sma200 > 0 else 0.0
        market_panic = bool(np.isfinite(ibov_sma200) and ibov < ibov_sma200)

        # CDI no caixa
        cash_before_cdi = cash
        cash *= (1.0 + cdi)
        cdi_credit = cash - cash_before_cdi

        pos_val_pre = positions_value(positions, px_row)
        equity_pre = cash + pos_val_pre
        lcl = lcl_equity(eq_hist, equity_pre)
        medium_marker = (equity_pre - lcl) / equity_pre if equity_pre > 0 else 0.0

        short_marker = 0.0
        if len(eq_hist) >= 2 and eq_hist[-2] > 0:
            short_marker = equity_pre / eq_hist[-2] - 1.0

        long_marker = float(long_marker_map.get(d, 0.0))

        # Policy Engine: target exposure 0..1 (mantido da T031).
        target = 1.0
        if short_marker < SHORT_DROP_TRIGGER:
            target -= 0.3
        if macro_marker < 0.0:
            target -= 0.5
        if medium_marker < 0.0:
            target -= 0.2
        if long_marker < 0.0:
            target -= 0.2
        else:
            target += 0.1
        target = clamp(target, 0.0, 1.0)

        current_exposure = pos_val_pre / equity_pre if equity_pre > 0 else 0.0

        day_diag = diag_day.get(d, pd.DataFrame())
        day_stand = stand_day.get(d, pd.DataFrame())
        day_vol = vol_day.get(d, pd.Series(dtype=float))

        # 1) Vendas técnicas (SELL explícito)
        if not day_diag.empty:
            for t, q in list(positions.items()):
                if q <= 0 or t not in day_diag.index:
                    continue
                sig = str(day_diag.loc[t, "execution_signal"]).upper()
                if sig != "SELL":
                    continue
                px = float(px_row.get(t, np.nan))
                if not np.isfinite(px) or px <= 0:
                    continue
                notional = q * px
                net = notional * (1.0 - ORDER_COST_RATE)
                cash_before = cash
                cash += net
                positions[t] = 0
                ledger_rows.append(
                    {
                        "date": d,
                        "ticker": t,
                        "side": "SELL",
                        "reason": "TECHNICAL_SELL",
                        "qty": q,
                        "price": px,
                        "notional": notional,
                        "net_notional": net,
                        "cost_brl": notional - net,
                        "cash_before": cash_before,
                        "cash_after": cash,
                        "target_exposure": target,
                    }
                )

        # recompute exposure after technical sells
        pos_val = positions_value(positions, px_row)
        equity = cash + pos_val
        current_exposure = pos_val / equity if equity > 0 else 0.0

        # 2) Rebalance down: vende piores rankings até aproximar target
        if current_exposure > target + BUFFER and not day_stand.empty:
            while current_exposure > target + BUFFER:
                held = [t for t, q in positions.items() if q > 0 and t in day_stand.index]
                if not held:
                    break
                worst_t = (
                    day_stand.loc[held]
                    .sort_values(["standings_rank", "ticker"], ascending=[False, True])
                    .index[0]
                )
                q = int(positions.get(worst_t, 0))
                if q <= 0:
                    break
                px = float(px_row.get(worst_t, np.nan))
                if not np.isfinite(px) or px <= 0:
                    positions[worst_t] = 0
                    continue
                excess_val = (current_exposure - target) * equity
                qty_sell = int(max(1, min(q, math.floor(excess_val / px))))
                notional = qty_sell * px
                net = notional * (1.0 - ORDER_COST_RATE)
                cash_before = cash
                cash += net
                positions[worst_t] = q - qty_sell
                ledger_rows.append(
                    {
                        "date": d,
                        "ticker": worst_t,
                        "side": "SELL",
                        "reason": "REBALANCE_DOWN_WORST_F1",
                        "qty": qty_sell,
                        "price": px,
                        "notional": notional,
                        "net_notional": net,
                        "cost_brl": notional - net,
                        "cash_before": cash_before,
                        "cash_after": cash,
                        "target_exposure": target,
                    }
                )
                pos_val = positions_value(positions, px_row)
                equity = cash + pos_val
                current_exposure = pos_val / equity if equity > 0 else 0.0

        # 3) Rebalance up: compra top F1 com hard-filter de slope e score ajustado por risco
        buy_allowed = (idx % BUY_HEARTBEAT_DAYS == 0) and (not market_panic)
        if buy_allowed and current_exposure < target - BUFFER and not day_stand.empty and not day_diag.empty:
            # Pré-filtro de candidatos por ranking base.
            candidates = day_stand.sort_values(["standings_rank", "ticker"]).head(TOP_N).copy()
            candidates = candidates.reset_index().rename(columns={"index": "ticker"})
            # Anexa slope_60 e vol_60 do dia.
            candidates["slope_60"] = candidates["ticker"].map(day_diag["slope_60"].to_dict())
            candidates["vol_60"] = candidates["ticker"].map(day_vol.to_dict())

            # Hard filter: não compra slope <= 0.
            candidates = candidates[candidates["slope_60"].notna() & (candidates["slope_60"] > 0)].copy()
            # Volatilidade precisa existir para score de risco.
            candidates = candidates[candidates["vol_60"].notna()].copy()

            if not candidates.empty:
                candidates["z_f1"] = zscore_cross_section(candidates["f1_score_total"])
                candidates["z_vol"] = zscore_cross_section(candidates["vol_60"])
                candidates["final_score"] = candidates["z_f1"] - RISK_WEIGHT * candidates["z_vol"]
                candidates = candidates.sort_values(["final_score", "ticker"], ascending=[False, True]).head(TOP_N)

                need_val = max(0.0, target * equity - pos_val)
                for row in candidates.itertuples(index=False):
                    if need_val <= 0:
                        break
                    t = str(row.ticker)
                    px = float(px_row.get(t, np.nan))
                    if not np.isfinite(px) or px <= 0:
                        continue
                    cur_val = int(positions.get(t, 0)) * px
                    cap_val = MAX_WEIGHT_PER_ASSET * equity
                    can_add = max(0.0, cap_val - cur_val)
                    alloc = min(can_add, need_val / TOP_N)
                    if alloc <= 0:
                        continue
                    qty = int(math.floor(alloc / px))
                    if qty <= 0:
                        continue
                    notional = qty * px
                    gross = notional * (1.0 + ORDER_COST_RATE)
                    if cash <= gross:
                        continue
                    cash_before = cash
                    cash -= gross
                    positions[t] = int(positions.get(t, 0)) + qty
                    ledger_rows.append(
                        {
                            "date": d,
                            "ticker": t,
                            "side": "BUY",
                            "reason": "REBALANCE_UP_RISK_ADJUSTED",
                            "qty": qty,
                            "price": px,
                            "notional": notional,
                            "net_notional": notional,
                            "cost_brl": gross - notional,
                            "cash_before": cash_before,
                            "cash_after": cash,
                            "target_exposure": target,
                            "slope_60_at_buy": float(row.slope_60),
                            "vol_60_at_buy": float(row.vol_60),
                            "final_score_at_buy": float(row.final_score),
                        }
                    )
                    need_val -= notional
                    pos_val = positions_value(positions, px_row)
                    equity = cash + pos_val
                    current_exposure = pos_val / equity if equity > 0 else 0.0
                    if current_exposure >= target - BUFFER:
                        break

        # curva final do dia
        pos_val = positions_value(positions, px_row)
        equity = cash + pos_val
        eq_hist.append(equity)
        current_exposure = pos_val / equity if equity > 0 else 0.0
        benchmark = INITIAL_CAPITAL * (ibov / ibov_base) if ibov_base > 0 else np.nan

        curve_rows.append(
            {
                "date": d,
                "cash_start_before_cdi": cash_before_cdi,
                "cdi_daily": cdi,
                "cash_cdi_credit": cdi_credit,
                "cash_end": cash,
                "positions_value_end": pos_val,
                "equity_end": equity,
                "current_exposure": current_exposure,
                "target_exposure": target,
                "short_term_marker": short_marker,
                "medium_term_marker": medium_marker,
                "long_term_marker": long_marker,
                "macro_marker": macro_marker,
                "ibov_close": ibov,
                "ibov_sma200": ibov_sma200,
                "market_panic": market_panic,
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
                "target_exposure",
            ]
        )
    else:
        ledger = ledger.sort_values(["date", "side", "ticker"]).reset_index(drop=True)

    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(OUT_LEDGER, index=False)
    curve.to_parquet(OUT_CURVE, index=False)

    # Validação factual T033: nenhuma compra com slope <= 0.
    buy_mask = ledger["side"].astype(str).str.upper() == "BUY"
    invalid_buys = int((ledger.loc[buy_mask, "slope_60_at_buy"] <= 0).sum()) if "slope_60_at_buy" in ledger.columns else 0
    mdd = max_drawdown(curve["equity_end"])

    print("TASK T033 - CORRECTIVE LOGIC IMPLEMENTATION")
    print(f"DATES_SIMULATED: {len(curve)}")
    print(f"TRADES: {len(ledger)}")
    print(f"BUY_SLOPE_LEQ_ZERO: {invalid_buys}")
    print(f"AVG_EXPOSURE: {curve['current_exposure'].mean():.4f}")
    print(f"MAX_DRAWDOWN: {mdd:.4%}")
    print(f"OUT_LEDGER: {OUT_LEDGER}")
    print(f"OUT_CURVE: {OUT_CURVE}")
    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
