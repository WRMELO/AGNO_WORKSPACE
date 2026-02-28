#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env!")


TASK_ID = "T063-MARKET-SLOPE-REENTRY-ABLATION-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INITIAL_CAPITAL = 100_000.0
ORDER_COST_RATE = 0.00025
TOP_N = 10
TARGET_PCT = 0.10
MAX_PCT = 0.15
START_DATE = pd.Timestamp("2018-07-02")

MU_WINDOW = 62
MU_MIN_PERIODS = 20
SLOPE_WINDOWS = [10, 20, 30]
IN_HYST_DAYS_GRID = [2, 3, 4]
OUT_HYST_DAYS_GRID = [2, 3, 4, 5]

CADENCE_DAYS_FIXED = 81
BUY_TURNOVER_CAP_RATIO_FIXED: float | None = None

REENTRY_SUBPERIOD_START = pd.Timestamp("2025-10-01")
REENTRY_SUBPERIOD_END = pd.Timestamp("2026-02-26")

THRESHOLDS = {
    "MDD_total_min": -0.30,
    "turnover_total_total_max": 8.0,
    "reentry_subperiod_time_in_market_min": 0.05,
}

CANONICAL_FILE = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet"
MACRO_FILE = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
BLACKLIST_FILE = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
SCORES_FILE = ROOT / "src/data_engine/features/T037_M3_SCORES_DAILY.parquet"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/T063_REENTRY_HYST_ABLATION_RESULTS.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T063_REENTRY_SELECTED_CONFIG.json"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T063_PORTFOLIO_CURVE_REENTRY_FIX.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T063_PORTFOLIO_LEDGER_REENTRY_FIX.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T063_BASELINE_SUMMARY_REENTRY_FIX.json"

OUT_REPORT = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V1_evidence"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_FEASIBILITY = OUT_EVIDENCE_DIR / "feasibility_snapshot.json"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = "- 2026-02-28T19:30:00Z | STRATEGY: T063-MARKET-SLOPE-REENTRY-ABLATION-V1 EXEC. Artefatos: outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V1_report.md; outputs/governanca/T063-MARKET-SLOPE-REENTRY-ABLATION-V1_manifest.json; src/data_engine/portfolio/T063_REENTRY_SELECTED_CONFIG.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if np.isfinite(v) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def rolling_slope(series: pd.Series, window: int) -> pd.Series:
    y = pd.to_numeric(series, errors="coerce").astype(float)
    out = np.full(len(y), np.nan, dtype=float)
    if window < 2:
        return pd.Series(out, index=y.index)
    x = np.arange(window, dtype=float)
    x_center = x - x.mean()
    denom = float(np.sum(x_center**2))
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
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if eq.empty:
        return 0.0
    roll_max = eq.cummax()
    dd = eq / roll_max - 1.0
    return float(dd.min())


def compute_metrics(equity: pd.Series) -> dict[str, float]:
    eq = pd.to_numeric(equity, errors="coerce").astype(float)
    if eq.empty or eq.iloc[0] <= 0:
        return {"ret_total": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
    ret_total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    daily = eq.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    years = max((len(eq) - 1) / 252.0, 1e-12)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = max_drawdown(eq)
    vol = float(daily.std(ddof=0))
    sharpe = float(np.sqrt(252.0) * daily.mean() / vol) if vol > 0 else np.nan
    return {"ret_total": ret_total, "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def load_blacklist() -> set[str]:
    with BLACKLIST_FILE.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return set(payload["tickers_list"])


def build_rule_proxy_maps(df: pd.DataFrame) -> tuple[dict[tuple[str, pd.Timestamp], bool], dict[tuple[str, pd.Timestamp], bool], dict[tuple[str, pd.Timestamp], bool]]:
    def col(name: str) -> pd.Series:
        if name in df.columns:
            return df[name]
        return pd.Series(np.nan, index=df.index)

    we_rule_01 = (
        col("i_value").notna()
        & col("i_lcl").notna()
        & col("i_ucl").notna()
        & ((col("i_value") < col("i_lcl")) | (col("i_value") > col("i_ucl")))
    )
    amp_out = (
        ((col("mr_value").notna() & col("mr_ucl").notna() & (col("mr_value") > col("mr_ucl"))))
        | ((col("r_value").notna() & col("r_ucl").notna() & (col("r_value") > col("r_ucl"))))
    )
    xbar_out = (
        col("xbar_value").notna()
        & col("xbar_lcl").notna()
        & col("xbar_ucl").notna()
        & ((col("xbar_value") < col("xbar_lcl")) | (col("xbar_value") > col("xbar_ucl")))
    )
    any_we = we_rule_01 | amp_out | xbar_out
    strong_rule = we_rule_01 | amp_out
    in_control = ~any_we

    any_rule_map: dict[tuple[str, pd.Timestamp], bool] = {}
    strong_rule_map: dict[tuple[str, pd.Timestamp], bool] = {}
    in_control_map: dict[tuple[str, pd.Timestamp], bool] = {}
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


@dataclass
class EngineData:
    px_wide: pd.DataFrame
    z_wide: pd.DataFrame
    any_rule_map: dict[tuple[str, pd.Timestamp], bool]
    strong_rule_map: dict[tuple[str, pd.Timestamp], bool]
    in_control_map: dict[tuple[str, pd.Timestamp], bool]
    macro_day: pd.DataFrame
    scores_by_day: dict[pd.Timestamp, pd.DataFrame]
    sim_dates: list[pd.Timestamp]
    ibov_base: float


def prepare_engine_data() -> EngineData:
    blacklist = load_blacklist()
    canonical = pd.read_parquet(CANONICAL_FILE)
    canonical["ticker"] = canonical["ticker"].astype(str).str.upper().str.strip()
    canonical["date"] = pd.to_datetime(canonical["date"], errors="coerce").dt.normalize()
    canonical = canonical.dropna(subset=["ticker", "date", "close_operational"]).copy()

    prices = canonical[~canonical["ticker"].isin(blacklist)].copy()
    px_wide = (
        prices.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first")
        .sort_index()
        .ffill()
    )
    logret_wide = np.log(px_wide / px_wide.shift(1))
    mu = logret_wide.rolling(window=60, min_periods=20).mean()
    sd = logret_wide.rolling(window=60, min_periods=20).std(ddof=0)
    z_wide = (logret_wide - mu) / sd.replace(0.0, np.nan)

    any_rule_map, strong_rule_map, in_control_map = build_rule_proxy_maps(prices)

    macro = pd.read_parquet(MACRO_FILE)
    macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
    macro = macro.dropna(subset=["date", "ibov_close", "cdi_log_daily"]).sort_values("date")
    macro_day = macro.set_index("date")

    scores_df = pd.read_parquet(SCORES_FILE)
    scores_df["date"] = pd.to_datetime(scores_df["date"], errors="coerce").dt.normalize()
    scores_by_day: dict[pd.Timestamp, pd.DataFrame] = {}
    for d, g in scores_df.groupby("date", sort=True):
        scores_by_day[pd.Timestamp(d)] = g.set_index("ticker")

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [pd.Timestamp(d) for d in sim_dates if pd.Timestamp(d) >= START_DATE]
    if not sim_dates:
        raise RuntimeError("Sem datas em comum para simulacao.")
    ibov_base = float(macro_day.loc[sim_dates[0], "ibov_close"])

    return EngineData(
        px_wide=px_wide,
        z_wide=z_wide,
        any_rule_map=any_rule_map,
        strong_rule_map=strong_rule_map,
        in_control_map=in_control_map,
        macro_day=macro_day,
        scores_by_day=scores_by_day,
        sim_dates=sim_dates,
        ibov_base=ibov_base,
    )


def compute_market_mu_slope(engine: EngineData, slope_window: int) -> pd.Series:
    ibov_close = pd.to_numeric(engine.macro_day.loc[engine.sim_dates, "ibov_close"], errors="coerce").astype(float)
    ibov_lr = np.log(ibov_close / ibov_close.shift(1)).fillna(0.0)
    mu = ibov_lr.rolling(MU_WINDOW, min_periods=MU_MIN_PERIODS).mean().fillna(0.0)
    return rolling_slope(mu, slope_window).fillna(0.0)


def participation_metrics(curve: pd.DataFrame) -> dict[str, float]:
    c = curve.copy()
    c["equity_end"] = pd.to_numeric(c["equity_end"], errors="coerce").astype(float)
    c["cash_end"] = pd.to_numeric(c["cash_end"], errors="coerce").astype(float)
    c["positions_value_end"] = pd.to_numeric(c["positions_value_end"], errors="coerce").astype(float)
    c["exposure"] = pd.to_numeric(c["exposure"], errors="coerce").astype(float).fillna(0.0)
    cash_weight = (c["cash_end"] / c["equity_end"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return {
        "time_in_market_frac": float((c["exposure"] > 0).mean()),
        "avg_exposure": float(c["exposure"].mean()),
        "days_cash_ge_090_frac": float((cash_weight >= 0.90).mean()),
        "days_defensive_frac": float(pd.to_numeric(c["regime_defensivo"], errors="coerce").fillna(False).astype(bool).mean()),
    }


def turnover_total(ledger: pd.DataFrame, curve: pd.DataFrame) -> float:
    if ledger.empty:
        return 0.0
    l = ledger.copy()
    l["notional"] = pd.to_numeric(l.get("notional", np.nan), errors="coerce").astype(float)
    traded = float(l["notional"].fillna(0.0).abs().sum())
    avg_eq = float(pd.to_numeric(curve["equity_end"], errors="coerce").astype(float).mean())
    return float(traded / avg_eq) if avg_eq > 0 else float("nan")


def subperiod_time_in_market(curve: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> float:
    c = curve.copy()
    c["date"] = pd.to_datetime(c["date"], errors="coerce").dt.normalize()
    c = c[(c["date"] >= start) & (c["date"] <= end)].copy()
    if c.empty:
        return float("nan")
    exp = pd.to_numeric(c["exposure"], errors="coerce").astype(float).fillna(0.0)
    return float((exp > 0).mean())


def run_candidate(engine: EngineData, slope_window: int, in_hyst: int, out_hyst: int, cadence_days: int, buy_turnover_cap_ratio: float | None) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    px_wide = engine.px_wide
    z_wide = engine.z_wide
    macro_day = engine.macro_day
    scores_by_day = engine.scores_by_day
    sim_dates = engine.sim_dates
    market_mu_slope = compute_market_mu_slope(engine, slope_window=slope_window)

    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    ledger_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []

    trend_down = False
    in_streak = 0
    out_streak = 0
    num_switches = 0

    blocked_reentry: set[str] = set()
    pending_sell_exec: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    n_reentry_blocks = 0
    blocked_buy_events_regime = 0

    for day_idx, d in enumerate(sim_dates):
        px_row = px_wide.loc[d]
        m = macro_day.loc[d]
        ibov = float(m["ibov_close"])

        for order in pending_sell_exec.get(d, []):
            ticker = str(order["ticker"])
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
            ledger_rows.append({
                "date": d, "ticker": ticker, "side": "SELL",
                "reason": f"CEP_SEVERITY_GATE_S{score}",
                "qty": qty_sell, "price": px,
                "notional": notional, "net_notional": notional - fee,
                "cost_brl": fee,
                "cash_before": cash_before, "cash_after": cash,
                "blocked_by_guardrail": False,
            })
            blocked_reentry.add(ticker)

        cdi_log = float(m["cdi_log_daily"]) if pd.notna(m["cdi_log_daily"]) else 0.0
        cdi_daily = np.exp(cdi_log) - 1.0
        cash_before_cdi = cash
        cash *= (1.0 + cdi_daily)
        cdi_credit = cash - cash_before_cdi

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

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
                "blocked_by_guardrail": False,
            })

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        prev_regime = bool(trend_down)
        slope = float(market_mu_slope.loc[d]) if d in market_mu_slope.index else 0.0
        if not trend_down:
            in_streak = in_streak + 1 if slope < 0.0 else 0
            if in_streak >= in_hyst:
                trend_down = True
                in_streak = 0
                out_streak = 0
        else:
            out_streak = out_streak + 1 if slope > 0.0 else 0
            if out_streak >= out_hyst:
                trend_down = False
                out_streak = 0
                in_streak = 0
        regime_defensivo = bool(trend_down)
        if regime_defensivo != prev_regime:
            num_switches += 1

        candidates: list[dict[str, Any]] = []
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
            if engine.any_rule_map.get(key, False):
                rule_evidence += 1
            if engine.strong_rule_map.get(key, False):
                rule_evidence += 2
            score = int(min(6, band + persistence + rule_evidence))
            if regime_defensivo and (z0 < 0.0) and (score >= 4):
                candidates.append({"ticker": ticker, "score": score})

        if candidates:
            selected = sorted(candidates, key=lambda c: (-c["score"], c["ticker"]))[:5]
            d_exec = sim_dates[day_idx + 1] if day_idx + 1 < len(sim_dates) else None
            if d_exec is not None:
                pending = pending_sell_exec.setdefault(d_exec, [])
                for c in selected:
                    sell_pct = score_to_sell_pct(int(c["score"]))
                    if sell_pct > 0:
                        pending.append({"ticker": c["ticker"], "score": int(c["score"]), "sell_pct": int(sell_pct)})

        if blocked_reentry:
            candidate_tickers = {c["ticker"] for c in candidates}
            to_remove = []
            for ticker in blocked_reentry:
                if engine.in_control_map.get((ticker, d), False) and ticker not in candidate_tickers:
                    to_remove.append(ticker)
            for ticker in to_remove:
                blocked_reentry.discard(ticker)

        buy_day = day_idx % cadence_days == 0
        daily_buy_notional = 0.0
        if buy_turnover_cap_ratio is None:
            buy_budget = float("inf")
        else:
            buy_budget = float(max(0.0, buy_turnover_cap_ratio * max(equity_mid, 0.0)))
        blocked_budget_events_day = 0
        blocked_notional_day = 0.0

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
                if cur_val >= target_val:
                    continue
                buy_val = max(0.0, target_val - cur_val)
                qty_buy = int(math.floor(buy_val / px))
                if qty_buy <= 0:
                    continue
                notional = qty_buy * px
                fee = notional * ORDER_COST_RATE
                if notional + fee > cash:
                    continue
                if daily_buy_notional + notional > buy_budget:
                    blocked_budget_events_day += 1
                    blocked_notional_day += notional
                    continue
                cash_before = cash
                cash -= notional + fee
                positions[ticker] = cur_qty + qty_buy
                daily_buy_notional += notional
                ledger_rows.append({
                    "date": d, "ticker": ticker, "side": "BUY",
                    "reason": "M3_TOPN",
                    "qty": qty_buy, "price": px,
                    "notional": notional, "net_notional": notional,
                    "cost_brl": fee,
                    "cash_before": cash_before, "cash_after": cash,
                    "blocked_by_guardrail": False,
                })
        elif buy_day and d in scores_by_day and regime_defensivo:
            blocked_buy_events_regime += 1

        pos_val_end = positions_value(positions, px_row)
        equity_end = cash + pos_val_end
        exposure = pos_val_end / equity_end if equity_end > 0 else 0.0
        benchmark = INITIAL_CAPITAL * (ibov / engine.ibov_base) if engine.ibov_base > 0 else np.nan
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
            "regime_defensivo": bool(regime_defensivo),
            "market_mu_slope": float(slope),
            "num_switches_cumsum": int(num_switches),
            "n_blocked_reentry": int(len(blocked_reentry)),
            "blocked_buy_events_regime_cumsum": int(blocked_buy_events_regime),
            "n_reentry_blocks_cumsum": int(n_reentry_blocks),
            "blocked_buy_notional_day": float(blocked_notional_day),
            "n_buy_blocked_budget_day": int(blocked_budget_events_day),
            "buy_cadence_days_effective": int(cadence_days),
            "buy_turnover_cap_ratio_effective": float(buy_turnover_cap_ratio) if buy_turnover_cap_ratio is not None else np.nan,
        })

    ledger = pd.DataFrame(ledger_rows)
    if not ledger.empty:
        ledger = ledger.sort_values(["date", "side", "ticker"]).reset_index(drop=True)
    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
    extra = {
        "num_switches": int(curve["num_switches_cumsum"].max()) if not curve.empty else 0,
        "blocked_buy_events_regime": int(curve["blocked_buy_events_regime_cumsum"].max()) if not curve.empty else 0,
        "n_reentry_blocks": int(curve["n_reentry_blocks_cumsum"].max()) if not curve.empty else 0,
    }
    return ledger, curve, extra


def update_changelog_one_line(line: str) -> bool:
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_size = len(before.encode("utf-8"))
    text = before
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    after_size = len(text.encode("utf-8"))
    delta = after_size - before_size
    return delta == len((line.rstrip("\n") + "\n").encode("utf-8")) and text.endswith(line.rstrip("\n") + "\n")


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    print("MODEL ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidência explícita no chat)")
    gates: dict[str, str] = {}
    retry_log: list[str] = []

    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    try:
        engine = prepare_engine_data()
        gates["G0_INPUTS_PRESENT"] = "PASS"
    except Exception as e:
        gates["G0_INPUTS_PRESENT"] = "FAIL"
        print("STEP GATES:")
        for k, v in gates.items():
            print(f"- {k}: {v} ({type(e).__name__}: {e})")
        print("RETRY LOG:")
        print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    candidates = []
    for sw in SLOPE_WINDOWS:
        for ih in IN_HYST_DAYS_GRID:
            for oh in OUT_HYST_DAYS_GRID:
                candidates.append({
                    "candidate_id": f"SW{sw}_IN{ih}_OUT{oh}",
                    "slope_window": int(sw),
                    "in_hyst_days": int(ih),
                    "out_hyst_days": int(oh),
                    "cadence_days": int(CADENCE_DAYS_FIXED),
                    "buy_turnover_cap_ratio": None,
                })
    write_json_strict(OUT_CANDIDATE_SET, {"task_id": TASK_ID, "candidates": candidates})

    rows: list[dict[str, Any]] = []
    feasible_rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_key: tuple | None = None

    for c in candidates:
        ledger, curve, extra = run_candidate(
            engine=engine,
            slope_window=int(c["slope_window"]),
            in_hyst=int(c["in_hyst_days"]),
            out_hyst=int(c["out_hyst_days"]),
            cadence_days=int(c["cadence_days"]),
            buy_turnover_cap_ratio=None if BUY_TURNOVER_CAP_RATIO_FIXED is None else float(BUY_TURNOVER_CAP_RATIO_FIXED),
        )
        m = compute_metrics(curve["equity_end"])
        p = participation_metrics(curve)
        t_total = turnover_total(ledger, curve)
        t_reentry = subperiod_time_in_market(curve, REENTRY_SUBPERIOD_START, REENTRY_SUBPERIOD_END)
        equity_final = float(pd.to_numeric(curve["equity_end"], errors="coerce").astype(float).iloc[-1])

        row = {
            "candidate_id": c["candidate_id"],
            "slope_window": int(c["slope_window"]),
            "in_hyst_days": int(c["in_hyst_days"]),
            "out_hyst_days": int(c["out_hyst_days"]),
            "equity_final": equity_final,
            "CAGR": float(m["cagr"]),
            "MDD": float(m["mdd"]),
            "Sharpe": float(m["sharpe"]),
            "turnover_total": float(t_total),
            "time_in_market_frac": float(p["time_in_market_frac"]),
            "avg_exposure": float(p["avg_exposure"]),
            "days_cash_ge_090_frac": float(p["days_cash_ge_090_frac"]),
            "days_defensive_frac": float(p["days_defensive_frac"]),
            "reentry_subperiod_time_in_market": float(t_reentry),
            "num_switches": int(extra.get("num_switches", 0)),
        }
        rows.append(row)

        feasible = (
            np.isfinite(row["MDD"]) and row["MDD"] >= THRESHOLDS["MDD_total_min"]
            and np.isfinite(row["turnover_total"]) and row["turnover_total"] <= THRESHOLDS["turnover_total_total_max"]
            and np.isfinite(row["reentry_subperiod_time_in_market"]) and row["reentry_subperiod_time_in_market"] >= THRESHOLDS["reentry_subperiod_time_in_market_min"]
        )
        if feasible:
            feasible_rows.append(row)
            key = (
                -row["equity_final"],
                -row["MDD"],
                row["turnover_total"],
                row["days_cash_ge_090_frac"],
                row["candidate_id"],
            )
            if best_key is None or key < best_key:
                best_key = key
                best = {"cfg": c, "row": row, "ledger": ledger, "curve": curve}

    ablation_df = pd.DataFrame(rows).sort_values(["equity_final"], ascending=False).reset_index(drop=True)
    OUT_ABLATION.parent.mkdir(parents=True, exist_ok=True)
    ablation_df.to_parquet(OUT_ABLATION, index=False)
    gates["G1_ABLATION_RESULTS_PRESENT"] = "PASS"

    write_json_strict(
        OUT_FEASIBILITY,
        {
            "task_id": TASK_ID,
            "thresholds": THRESHOLDS,
            "total_candidates": int(len(candidates)),
            "feasible_count": int(len(feasible_rows)),
            "feasible_candidate_ids": [r["candidate_id"] for r in feasible_rows],
        },
    )

    if best is None:
        gates["G2_FEASIBLE_NONEMPTY"] = "FAIL"
        OUT_REPORT.write_text(
            "\n".join(
                [
                    f"# {TASK_ID} Report",
                    "",
                    "## Resultado",
                    "",
                    f"- feasible_count: 0 / {len(candidates)}",
                    "- Nenhum candidato atingiu constraints hard.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ch_ok = update_changelog_one_line(TRACEABILITY_LINE)
        gates["G_CHLOG_UPDATED"] = "PASS" if ch_ok else "FAIL"
        write_json_strict(
            OUT_MANIFEST,
            {
                "task_id": TASK_ID,
                "hashes_sha256": {
                    str(OUT_ABLATION): sha256_file(OUT_ABLATION),
                    str(OUT_FEASIBILITY): sha256_file(OUT_FEASIBILITY),
                    str(OUT_REPORT): sha256_file(OUT_REPORT),
                    str(CHANGELOG_PATH): sha256_file(CHANGELOG_PATH),
                    str(Path(__file__).resolve()): sha256_file(Path(__file__).resolve()),
                },
                "inputs_consumed": [str(CANONICAL_FILE), str(MACRO_FILE), str(BLACKLIST_FILE), str(SCORES_FILE), str(Path(__file__).resolve())],
                "outputs_produced": [str(OUT_ABLATION), str(OUT_FEASIBILITY), str(OUT_REPORT), str(OUT_MANIFEST), str(CHANGELOG_PATH)],
            },
        )
        gates["Gx_HASH_MANIFEST_PRESENT"] = "PASS"
        print("STEP GATES:")
        for k, v in gates.items():
            print(f"- {k}: {v}")
        print("RETRY LOG:")
        print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    gates["G2_FEASIBLE_NONEMPTY"] = "PASS"

    cfg = best["cfg"]
    row = best["row"]
    ledger = best["ledger"]
    curve = best["curve"]

    write_json_strict(
        OUT_SELECTED_CFG,
        {
            "task_id": TASK_ID,
            "selected_candidate_id": cfg["candidate_id"],
            "cadence_days": int(cfg["cadence_days"]),
            "buy_turnover_cap_ratio": cfg["buy_turnover_cap_ratio"],
            "market_mu_window": int(MU_WINDOW),
            "market_slope_window": int(cfg["slope_window"]),
            "in_hyst_days": int(cfg["in_hyst_days"]),
            "out_hyst_days": int(cfg["out_hyst_days"]),
            "thresholds": THRESHOLDS,
        },
    )
    curve.to_parquet(OUT_CURVE, index=False)
    ledger.to_parquet(OUT_LEDGER, index=False)
    write_json_strict(
        OUT_SUMMARY,
        {
            "task_id": TASK_ID,
            "selected_candidate_id": cfg["candidate_id"],
            "equity_final": float(row["equity_final"]),
            "cagr": float(row["CAGR"]),
            "mdd": float(row["MDD"]),
            "sharpe": float(row["Sharpe"]),
            "turnover_total": float(row["turnover_total"]),
            "time_in_market_frac": float(row["time_in_market_frac"]),
            "avg_exposure": float(row["avg_exposure"]),
            "days_cash_ge_090_frac": float(row["days_cash_ge_090_frac"]),
            "days_defensive_frac": float(row["days_defensive_frac"]),
            "reentry_subperiod_time_in_market": float(row["reentry_subperiod_time_in_market"]),
            "num_switches": int(row["num_switches"]),
        },
    )
    write_json_strict(
        OUT_SELECTION_RULE,
        {
            "task_id": TASK_ID,
            "constraints": THRESHOLDS,
            "selection_order": [
                "equity_final DESC",
                "MDD DESC",
                "turnover_total ASC",
                "days_cash_ge_090_frac ASC",
                "candidate_id ASC",
            ],
            "selected_candidate_id": cfg["candidate_id"],
        },
    )

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Objetivo",
        "",
        "- Corrigir armadilha de reentrada do T044 usando regime orientado por Mercado (Ibov) + histerese ablada.",
        "",
        "## 2) Grid testado",
        "",
        f"- SLOPE_WINDOWS={SLOPE_WINDOWS}",
        f"- IN_HYST_DAYS_GRID={IN_HYST_DAYS_GRID}",
        f"- OUT_HYST_DAYS_GRID={OUT_HYST_DAYS_GRID}",
        f"- cadence_days_fixed={CADENCE_DAYS_FIXED}",
        f"- buy_turnover_cap_ratio_fixed={BUY_TURNOVER_CAP_RATIO_FIXED}",
        "",
        "## 3) Constraints hard",
        "",
        json.dumps(THRESHOLDS, indent=2, sort_keys=True),
        "",
        "## 4) Seleção",
        "",
        f"- selected_candidate_id: {cfg['candidate_id']}",
        f"- market_slope_window: {cfg['slope_window']}",
        f"- IN/OUT: {cfg['in_hyst_days']}/{cfg['out_hyst_days']}",
        "",
        "## 5) Métricas do winner",
        "",
        f"- equity_final: {row['equity_final']:.2f}",
        f"- CAGR: {row['CAGR']:.6f}",
        f"- MDD: {row['MDD']:.6f}",
        f"- Sharpe: {row['Sharpe']:.6f}",
        f"- turnover_total: {row['turnover_total']:.6f}",
        f"- time_in_market_frac: {row['time_in_market_frac']:.6f}",
        f"- avg_exposure: {row['avg_exposure']:.6f}",
        f"- days_cash_ge_090_frac: {row['days_cash_ge_090_frac']:.6f}",
        f"- days_defensive_frac: {row['days_defensive_frac']:.6f}",
        f"- reentry_subperiod_time_in_market: {row['reentry_subperiod_time_in_market']:.6f}",
        "",
    ]
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    gates["G3_SELECTED_ARTIFACTS_PRESENT"] = "PASS"

    ch_ok = update_changelog_one_line(TRACEABILITY_LINE)
    gates["G_CHLOG_UPDATED"] = "PASS" if ch_ok else "FAIL"

    script_path = Path(__file__).resolve()
    inputs = [CANONICAL_FILE, MACRO_FILE, BLACKLIST_FILE, SCORES_FILE, script_path]
    outputs = [
        OUT_ABLATION,
        OUT_SELECTED_CFG,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_REPORT,
        OUT_CANDIDATE_SET,
        OUT_SELECTION_RULE,
        OUT_FEASIBILITY,
        CHANGELOG_PATH,
        OUT_MANIFEST,
    ]
    hashes = {str(p): sha256_file(p) for p in inputs + [p for p in outputs if p != OUT_MANIFEST]}
    write_json_strict(
        OUT_MANIFEST,
        {
            "task_id": TASK_ID,
            "hashes_sha256": hashes,
            "inputs_consumed": [str(p) for p in inputs],
            "outputs_produced": [str(p) for p in outputs],
        },
    )
    gates["Gx_HASH_MANIFEST_PRESENT"] = "PASS" if OUT_MANIFEST.exists() else "FAIL"

    print("STEP GATES:")
    for k, v in gates.items():
        print(f"- {k}: {v}")
    print("RETRY LOG:")
    if retry_log:
        for r in retry_log:
            print(f"- {r}")
    else:
        print("- none")
    print("ARTIFACT LINKS:")
    print(f"- {OUT_ABLATION}")
    print(f"- {OUT_SELECTED_CFG}")
    print(f"- {OUT_CURVE}")
    print(f"- {OUT_LEDGER}")
    print(f"- {OUT_SUMMARY}")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_CANDIDATE_SET}")
    print(f"- {OUT_SELECTION_RULE}")
    print(f"- {OUT_FEASIBILITY}")
    print(f"- {OUT_MANIFEST}")

    overall_pass = all(v == "PASS" for v in gates.values())
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
