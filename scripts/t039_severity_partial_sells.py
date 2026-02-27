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

ZSCORE_LOOKBACK = 60
ZSCORE_MIN_PERIODS = 20
SCORE_THRESHOLD = 4
SCORE_CAP = 6
TOP_K_SELL = 5

CANONICAL_FILE = Path("src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet")
MACRO_FILE = Path("src/data_engine/ssot/SSOT_MACRO.parquet")
BLACKLIST_FILE = Path("src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json")
SCORES_FILE = Path("src/data_engine/features/T037_M3_SCORES_DAILY.parquet")
T037_SUMMARY_FILE = Path("src/data_engine/portfolio/T037_BASELINE_SUMMARY.json")
T038_SUMMARY_FILE = Path("src/data_engine/portfolio/T038_BASELINE_SUMMARY.json")

OUT_LEDGER = Path("src/data_engine/portfolio/T039_PORTFOLIO_LEDGER.parquet")
OUT_CURVE = Path("src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet")
OUT_SUMMARY = Path("src/data_engine/portfolio/T039_BASELINE_SUMMARY.json")


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


def band_from_z(z: float) -> int:
    if not np.isfinite(z) or z >= -1.0:
        return 0
    if -2.0 <= z < -1.0:
        return 1
    if -3.0 <= z < -2.0:
        return 2
    return 3


def score_to_sell_pct(score: int) -> int:
    if score >= 6:
        return 100
    if score == 5:
        return 50
    if score == 4:
        return 25
    return 0


def build_rule_proxy_maps(df: pd.DataFrame) -> tuple[dict[tuple[str, pd.Timestamp], bool], dict[tuple[str, pd.Timestamp], bool], dict[tuple[str, pd.Timestamp], bool]]:
    we_rule_01 = (
        df["i_value"].notna()
        & df["i_lcl"].notna()
        & df["i_ucl"].notna()
        & ((df["i_value"] < df["i_lcl"]) | (df["i_value"] > df["i_ucl"]))
    )
    amp_out = (
        ((df["mr_value"].notna() & df["mr_ucl"].notna() & (df["mr_value"] > df["mr_ucl"])))
        | ((df["r_value"].notna() & df["r_ucl"].notna() & (df["r_value"] > df["r_ucl"])))
    )
    xbar_out = (
        df["xbar_value"].notna()
        & df["xbar_lcl"].notna()
        & df["xbar_ucl"].notna()
        & ((df["xbar_value"] < df["xbar_lcl"]) | (df["xbar_value"] > df["xbar_ucl"]))
    )
    any_we = we_rule_01 | amp_out | xbar_out
    strong_rule = we_rule_01 | amp_out
    in_control = ~any_we

    any_rule_map = {}
    strong_rule_map = {}
    in_control_map = {}
    for row, any_v, strong_v, ctrl_v in zip(
        df[["ticker", "date"]].itertuples(index=False),
        any_we.to_numpy(),
        strong_rule.to_numpy(),
        in_control.to_numpy(),
    ):
        key = (str(row.ticker), pd.Timestamp(row.date))
        any_rule_map[key] = bool(any_v)
        strong_rule_map[key] = bool(strong_v)
        in_control_map[key] = bool(ctrl_v)
    return any_rule_map, strong_rule_map, in_control_map


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

    # Z-score rolling por ticker.
    mu = logret_wide.rolling(window=ZSCORE_LOOKBACK, min_periods=ZSCORE_MIN_PERIODS).mean()
    sd = logret_wide.rolling(window=ZSCORE_LOOKBACK, min_periods=ZSCORE_MIN_PERIODS).std(ddof=0)
    z_wide = (logret_wide - mu) / sd.replace(0.0, np.nan)

    # Mapas proxies Nelson/WE.
    any_rule_map, strong_rule_map, in_control_map = build_rule_proxy_maps(prices)

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
    portfolio_logret_hist: list[float] = []
    num_switches = 0
    blocked_buy_events = 0
    blocked_reentry: set[str] = set()
    n_reentry_blocks = 0

    pending_sell_exec: dict[pd.Timestamp, list[dict]] = {}

    total_severity_sells = 0
    total_partial_sells_25 = 0
    total_partial_sells_50 = 0
    total_partial_sells_100 = 0
    scores_at_sell: list[int] = []

    for day_idx, d in enumerate(sim_dates):
        px_row = px_wide.loc[d]
        m = macro_day.loc[d]
        ibov = float(m["ibov_close"])

        # 1) Executa vendas D+1 agendadas ANTES de CDI.
        for order in pending_sell_exec.get(d, []):
            ticker = order["ticker"]
            qty_cur = int(positions.get(ticker, 0))
            if qty_cur <= 0:
                continue
            px = float(px_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue
            sell_pct = int(order["sell_pct"])
            score = int(order["score"])

            qty_sell = int(math.floor(qty_cur * sell_pct / 100.0))
            if sell_pct >= 100:
                qty_sell = qty_cur
            if qty_sell <= 0:
                continue

            notional = qty_sell * px
            fee = notional * ORDER_COST_RATE
            cash_before = cash
            cash += notional - fee
            positions[ticker] = qty_cur - qty_sell

            reason = f"CEP_SEVERITY_GATE_S{score}"
            ledger_rows.append(
                {
                    "date": d,
                    "ticker": ticker,
                    "side": "SELL",
                    "reason": reason,
                    "qty": qty_sell,
                    "price": px,
                    "notional": notional,
                    "net_notional": notional - fee,
                    "cost_brl": fee,
                    "cash_before": cash_before,
                    "cash_after": cash,
                }
            )

            total_severity_sells += 1
            scores_at_sell.append(score)
            if sell_pct == 25:
                total_partial_sells_25 += 1
            elif sell_pct == 50:
                total_partial_sells_50 += 1
            elif sell_pct >= 100:
                total_partial_sells_100 += 1

            blocked_reentry.add(ticker)

        # 2) CDI no caixa.
        cdi_log = float(m["cdi_log_daily"]) if pd.notna(m["cdi_log_daily"]) else 0.0
        cdi_daily = np.exp(cdi_log) - 1.0
        cash_before_cdi = cash
        cash *= (1.0 + cdi_daily)
        cdi_credit = cash - cash_before_cdi

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # 3) Trim acima do máximo.
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

        # 4) Severity scoring no dia (candidatos em carteira).
        candidates: list[dict] = []
        for ticker, qty in positions.items():
            if qty <= 0:
                continue
            if ticker not in z_wide.columns:
                continue
            z0 = float(z_wide.loc[d, ticker]) if d in z_wide.index else np.nan
            if not np.isfinite(z0):
                continue
            z1 = np.nan
            z2 = np.nan
            # lookup dos dois dias anteriores da simulação.
            if day_idx >= 1:
                d1 = sim_dates[day_idx - 1]
                if d1 in z_wide.index:
                    z1 = float(z_wide.loc[d1, ticker])
            if day_idx >= 2:
                d2 = sim_dates[day_idx - 2]
                if d2 in z_wide.index:
                    z2 = float(z_wide.loc[d2, ticker])

            band = band_from_z(z0)
            neg_count = int(z0 < 0) + int(np.isfinite(z1) and z1 < 0) + int(np.isfinite(z2) and z2 < 0)
            persistence = 1 if neg_count >= 2 else 0
            if np.isfinite(z1) and z0 < -2.0 and z1 < -2.0:
                persistence += 1

            key = (ticker, d)
            rule_evidence = 0
            if any_rule_map.get(key, False):
                rule_evidence += 1
            if strong_rule_map.get(key, False):
                rule_evidence += 2

            score = int(min(SCORE_CAP, band + persistence + rule_evidence))
            candidate = bool(regime_defensivo and (z0 < 0.0) and (score >= SCORE_THRESHOLD))

            if candidate:
                candidates.append({"ticker": ticker, "score": score, "z": z0})

        # 5) Agendar vendas D+1 top-k.
        n_sell_candidates = len(candidates)
        avg_score_candidates = float(np.mean([c["score"] for c in candidates])) if candidates else np.nan
        if candidates:
            selected = sorted(candidates, key=lambda c: (-c["score"], c["ticker"]))[:TOP_K_SELL]
            d_exec = sim_dates[day_idx + 1] if day_idx + 1 < len(sim_dates) else None
            if d_exec is not None:
                pending = pending_sell_exec.setdefault(d_exec, [])
                for c in selected:
                    sell_pct = score_to_sell_pct(c["score"])
                    if sell_pct > 0:
                        pending.append(
                            {
                                "ticker": c["ticker"],
                                "score": int(c["score"]),
                                "sell_pct": int(sell_pct),
                            }
                        )

        # 6) Desbloqueio anti-reentry.
        if blocked_reentry:
            to_remove: list[str] = []
            candidate_tickers = {c["ticker"] for c in candidates}
            for ticker in blocked_reentry:
                if in_control_map.get((ticker, d), False) and ticker not in candidate_tickers:
                    to_remove.append(ticker)
            for ticker in to_remove:
                blocked_reentry.discard(ticker)

        # 7) Buy block por regime e anti-reentry.
        buy_day = day_idx % BUY_CADENCE_DAYS == 0
        if buy_day and d in scores_by_day and not regime_defensivo:
            day_scores = scores_by_day[d]
            top_candidates = day_scores[day_scores["m3_rank"] <= TOP_N].sort_values("m3_rank")
            for row in top_candidates.itertuples():
                ticker = str(row.Index)

                if ticker in blocked_reentry:
                    n_reentry_blocks += 1
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

        # 8) Curva diária e atualização do regime.
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
                "n_sell_candidates": n_sell_candidates,
                "n_blocked_reentry": len(blocked_reentry),
                "avg_score_candidates": avg_score_candidates,
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
    extra = {
        "num_switches": num_switches,
        "blocked_buy_events": blocked_buy_events,
        "total_severity_sells": total_severity_sells,
        "total_partial_sells_25": total_partial_sells_25,
        "total_partial_sells_50": total_partial_sells_50,
        "total_partial_sells_100": total_partial_sells_100,
        "avg_score_at_sell": float(np.mean(scores_at_sell)) if scores_at_sell else np.nan,
        "n_reentry_blocks": n_reentry_blocks,
    }
    return ledger, curve, extra


def main() -> None:
    for p in [CANONICAL_FILE, MACRO_FILE, BLACKLIST_FILE, SCORES_FILE, T037_SUMMARY_FILE, T038_SUMMARY_FILE]:
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
    with open(T038_SUMMARY_FILE, "r", encoding="utf-8") as f:
        t038 = json.load(f)

    print("TASK T039 — SEVERITY SCORE + PARTIAL SELLS")
    print(
        f"PARAMS: z={ZSCORE_LOOKBACK}/{ZSCORE_MIN_PERIODS}, score_threshold={SCORE_THRESHOLD}, top_k_sell={TOP_K_SELL}, "
        f"gate_hysteresis={HYSTERESIS_ENTER}-in/{HYSTERESIS_EXIT}-out"
    )
    print(f"BLACKLIST: {len(blacklist)} tickers excluidos")
    print()

    ledger, curve, extra = run_simulation(scores_df, canonical, macro, blacklist)

    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    curve.to_parquet(OUT_CURVE, index=False)
    ledger.to_parquet(OUT_LEDGER, index=False)

    portfolio_m = compute_metrics(curve["equity_end"])
    n_buys = int((ledger["side"] == "BUY").sum()) if not ledger.empty else 0
    n_sells = int((ledger["side"] == "SELL").sum()) if not ledger.empty else 0
    n_stress_sells = int(ledger["reason"].astype(str).str.startswith("CEP_SEVERITY_GATE_").sum()) if not ledger.empty else 0
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
        "task_id": "T039",
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
        "total_severity_sells": int(extra["total_severity_sells"]),
        "total_partial_sells_25": int(extra["total_partial_sells_25"]),
        "total_partial_sells_50": int(extra["total_partial_sells_50"]),
        "total_partial_sells_100": int(extra["total_partial_sells_100"]),
        "avg_score_at_sell": float(extra["avg_score_at_sell"]) if np.isfinite(extra["avg_score_at_sell"]) else np.nan,
        "n_reentry_blocks": int(extra["n_reentry_blocks"]),
        "blocked_buy_events": int(extra["blocked_buy_events"]),
        "t037_baseline": t037,
        "t038_baseline": t038,
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=True, indent=2)
        f.write("\n")

    print("COMPARISON T037 vs T038 vs T039")
    print(f"  panic_buys_mar2020: {t037['panic_buys_mar2020']} -> {t038['panic_buys_mar2020']} -> {summary['panic_buys_mar2020']}")
    print(f"  cagr: {t037['cagr']:.4f} -> {t038['cagr']:.4f} -> {summary['cagr']:.4f}")
    print(f"  mdd: {t037['mdd']:.4f} -> {t038['mdd']:.4f} -> {summary['mdd']:.4f}")
    print(f"  sharpe: {t037['sharpe']:.4f} -> {t038['sharpe']:.4f} -> {summary['sharpe']:.4f}")
    print(f"  cdi_growth_simple: {cdi_growth_simple:.6f}")
    print(f"  cdi_growth_logsum: {cdi_growth_log:.6f}")
    print(f"  cdi_growth_rel_err: {cdi_rel_err:.12f}")
    print(f"  severity sells: {summary['total_severity_sells']} (25%={summary['total_partial_sells_25']}, 50%={summary['total_partial_sells_50']}, 100%={summary['total_partial_sells_100']})")
    print(f"  num_switches: {summary['num_switches']}, days_defensive_pct: {summary['days_defensive_pct']:.4f}, reentry_blocks: {summary['n_reentry_blocks']}")
    print()
    print(f"OUT_LEDGER: {OUT_LEDGER}")
    print(f"OUT_CURVE: {OUT_CURVE}")
    print(f"OUT_SUMMARY: {OUT_SUMMARY}")
    print()

    if not np.isfinite(cdi_rel_err) or cdi_rel_err > 1e-6:
        raise RuntimeError(f"CDI sanity failed: rel_err={cdi_rel_err} exceeds 1e-6.")

    print("OVERALL STATUS: [[ PASS ]]")


if __name__ == "__main__":
    main()
