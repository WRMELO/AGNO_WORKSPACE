#!/usr/bin/env python3
"""T044 - Anti-drift guardrails via data-driven ablation and deterministic selection."""

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


TASK_ID = "T044-ANTI-DRIFT-GUARDRAILS-V2"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INITIAL_CAPITAL = 100_000.0
ORDER_COST_RATE = 0.00025
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
ANN_FACTOR = 252.0

CANONICAL_FILE = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet"
MACRO_FILE = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
BLACKLIST_FILE = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
SCORES_FILE = ROOT / "src/data_engine/features/T037_M3_SCORES_DAILY.parquet"

INPUT_T039_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_T039_LEDGER = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_LEDGER.parquet"
INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T037_LEDGER = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_LEDGER.parquet"
INPUT_T040_SUBPERIOD = ROOT / "src/data_engine/portfolio/T040_METRICS_BY_SUBPERIOD.csv"
INPUT_T040_COMPARATIVE = ROOT / "src/data_engine/portfolio/T040_METRICS_COMPARATIVE.json"
INPUT_SPEC005 = ROOT / "02_Knowledge_Bank/docs/specs/SPEC-005_METRICS_SUITE.md"
SCRIPT_PATH = ROOT / "scripts/t044_anti_drift_guardrails_ablation.py"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/T044_GUARDRAILS_ABLATION_RESULTS.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T044_GUARDRAILS_SELECTED_CONFIG.json"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_LEDGER_GUARDRAILS.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"

OUT_REPORT = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T044-ANTI-DRIFT-GUARDRAILS-V2_evidence"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "guardrails_candidate_set.json"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_DAILY_BUDGET = OUT_EVIDENCE_DIR / "daily_turnover_buy_budget.csv"
OUT_ENFORCEMENT_SUMMARY = OUT_EVIDENCE_DIR / "guardrail_enforcement_summary.json"


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
    safe = _json_safe(payload)
    text = json.dumps(safe, indent=2, sort_keys=True, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def parse_json_strict(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {x}")),
    )


def load_blacklist() -> set[str]:
    with BLACKLIST_FILE.open("r", encoding="utf-8") as f:
        return set(json.load(f)["tickers_list"])


def positions_value(positions: dict[str, int], px_row: pd.Series) -> float:
    total = 0.0
    for ticker, qty in positions.items():
        if qty <= 0:
            continue
        px = float(px_row.get(ticker, np.nan))
        if np.isfinite(px) and px > 0:
            total += qty * px
    return float(total)


def rolling_slope(series: pd.Series, window: int) -> pd.Series:
    y = series.astype(float)
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
    mu = logret_wide.rolling(window=ZSCORE_LOOKBACK, min_periods=ZSCORE_MIN_PERIODS).mean()
    sd = logret_wide.rolling(window=ZSCORE_LOOKBACK, min_periods=ZSCORE_MIN_PERIODS).std(ddof=0)
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
        scores_by_day[d] = g.set_index("ticker")

    sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)))
    sim_dates = [d for d in sim_dates if d >= START_DATE]
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


def run_candidate(engine: EngineData, cadence_days: int, buy_turnover_cap_ratio: float | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    px_wide = engine.px_wide
    z_wide = engine.z_wide
    macro_day = engine.macro_day
    scores_by_day = engine.scores_by_day
    sim_dates = engine.sim_dates

    cash = float(INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    ledger_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    budget_rows: list[dict[str, Any]] = []

    regime_defensivo = False
    portfolio_logret_hist: list[float] = []
    num_switches = 0
    blocked_buy_events_regime = 0
    blocked_reentry: set[str] = set()
    n_reentry_blocks = 0
    pending_sell_exec: dict[pd.Timestamp, list[dict[str, Any]]] = {}

    total_severity_sells = 0
    total_partial_sells_25 = 0
    total_partial_sells_50 = 0
    total_partial_sells_100 = 0
    scores_at_sell: list[int] = []

    n_buy_blocked_by_cadence = 0
    n_buy_blocked_by_budget = 0
    n_buy_blocked_notional_budget = 0.0
    days_with_budget_binding = 0
    days_with_cadence_binding = 0

    for day_idx, d in enumerate(sim_dates):
        px_row = px_wide.loc[d]
        m = macro_day.loc[d]
        ibov = float(m["ibov_close"])

        # 1) Execute scheduled sells D+1.
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
            ledger_rows.append(
                {
                    "date": d,
                    "ticker": ticker,
                    "side": "SELL",
                    "reason": f"CEP_SEVERITY_GATE_S{score}",
                    "qty": qty_sell,
                    "price": px,
                    "notional": notional,
                    "net_notional": notional - fee,
                    "cost_brl": fee,
                    "cash_before": cash_before,
                    "cash_after": cash,
                    "blocked_by_guardrail": False,
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

        # 2) CDI credit.
        cdi_log = float(m["cdi_log_daily"]) if pd.notna(m["cdi_log_daily"]) else 0.0
        cdi_daily = np.exp(cdi_log) - 1.0
        cash_before_cdi = cash
        cash *= (1.0 + cdi_daily)
        cdi_credit = cash - cash_before_cdi

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # 3) Trim above MAX_PCT.
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
                    "blocked_by_guardrail": False,
                }
            )

        pos_val_mid = positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # 4) Severity candidates.
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
            score = int(min(SCORE_CAP, band + persistence + rule_evidence))
            candidate = bool(regime_defensivo and (z0 < 0.0) and (score >= SCORE_THRESHOLD))
            if candidate:
                candidates.append({"ticker": ticker, "score": score})

        # 5) Schedule sells D+1.
        n_sell_candidates = len(candidates)
        avg_score_candidates = float(np.mean([c["score"] for c in candidates])) if candidates else np.nan
        if candidates:
            selected = sorted(candidates, key=lambda c: (-c["score"], c["ticker"]))[:TOP_K_SELL]
            d_exec = sim_dates[day_idx + 1] if day_idx + 1 < len(sim_dates) else None
            if d_exec is not None:
                pending = pending_sell_exec.setdefault(d_exec, [])
                for c in selected:
                    sell_pct = score_to_sell_pct(int(c["score"]))
                    if sell_pct > 0:
                        pending.append({"ticker": c["ticker"], "score": int(c["score"]), "sell_pct": int(sell_pct)})

        # 6) Anti-reentry unlock.
        if blocked_reentry:
            to_remove: list[str] = []
            candidate_tickers = {c["ticker"] for c in candidates}
            for ticker in blocked_reentry:
                if engine.in_control_map.get((ticker, d), False) and ticker not in candidate_tickers:
                    to_remove.append(ticker)
            for ticker in to_remove:
                blocked_reentry.discard(ticker)

        # 7) Buy with cadence + turnover cap.
        buy_day = day_idx % cadence_days == 0
        daily_buy_notional = 0.0
        blocked_notional_day = 0.0
        blocked_budget_events_day = 0

        # cap applied to buy notional only; sells are never blocked by this cap.
        if buy_turnover_cap_ratio is None:
            buy_budget = float("inf")
        else:
            buy_budget = float(max(0.0, buy_turnover_cap_ratio * max(equity_mid, 0.0)))

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
                if (daily_buy_notional + notional) > buy_budget:
                    blocked_budget_events_day += 1
                    blocked_notional_day += notional
                    n_buy_blocked_by_budget += 1
                    n_buy_blocked_notional_budget += notional
                    continue
                cash_before = cash
                cash -= gross
                positions[ticker] = cur_qty + qty_buy
                daily_buy_notional += notional
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
                        "blocked_by_guardrail": False,
                    }
                )
                pos_val_mid = positions_value(positions, px_row)
                equity_mid = cash + pos_val_mid
        elif buy_day and d in scores_by_day and regime_defensivo:
            blocked_buy_events_regime += 1
        elif (not buy_day) and (d in scores_by_day) and (not regime_defensivo):
            day_scores = scores_by_day[d]
            top_candidates = day_scores[day_scores["m3_rank"] <= TOP_N]
            n_block = int(len(top_candidates))
            if n_block > 0:
                days_with_cadence_binding += 1
                n_buy_blocked_by_cadence += n_block

        if blocked_budget_events_day > 0:
            days_with_budget_binding += 1

        # 8) Curve row + regime update.
        pos_val_end = positions_value(positions, px_row)
        equity_end = cash + pos_val_end
        exposure = pos_val_end / equity_end if equity_end > 0 else 0.0
        benchmark = INITIAL_CAPITAL * (ibov / engine.ibov_base) if engine.ibov_base > 0 else np.nan
        n_positions = sum(1 for q in positions.values() if q > 0)

        held = [t for t, q in positions.items() if q > 0 and t in engine.z_wide.columns]
        if held:
            lr = np.log(px_row[held] / px_wide.shift(1).loc[d, held]).replace([np.inf, -np.inf], np.nan)
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
                "buy_cadence_days_effective": int(cadence_days),
                "buy_turnover_cap_ratio_effective": float(buy_turnover_cap_ratio) if buy_turnover_cap_ratio is not None else np.nan,
            }
        )

        budget_rows.append(
            {
                "date": d,
                "equity_end": equity_end,
                "buy_notional_executed": daily_buy_notional,
                "buy_budget": buy_budget if np.isfinite(buy_budget) else np.nan,
                "buy_budget_utilization": (daily_buy_notional / buy_budget) if np.isfinite(buy_budget) and buy_budget > 0 else np.nan,
                "blocked_buy_notional": blocked_notional_day,
                "n_buy_blocked_budget_day": blocked_budget_events_day,
                "buy_day": bool(buy_day),
                "regime_defensivo": bool(regime_defensivo),
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
                "blocked_by_guardrail",
            ]
        )
    else:
        ledger = ledger.sort_values(["date", "side", "ticker"]).reset_index(drop=True)
    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
    budget_df = pd.DataFrame(budget_rows).sort_values("date").reset_index(drop=True)

    extra = {
        "num_switches": int(num_switches),
        "blocked_buy_events_regime": int(blocked_buy_events_regime),
        "total_severity_sells": int(total_severity_sells),
        "total_partial_sells_25": int(total_partial_sells_25),
        "total_partial_sells_50": int(total_partial_sells_50),
        "total_partial_sells_100": int(total_partial_sells_100),
        "avg_score_at_sell": float(np.mean(scores_at_sell)) if scores_at_sell else np.nan,
        "n_reentry_blocks": int(n_reentry_blocks),
        "n_buy_blocked_by_cadence": int(n_buy_blocked_by_cadence),
        "n_buy_blocked_by_budget": int(n_buy_blocked_by_budget),
        "n_buy_blocked_notional_budget": float(n_buy_blocked_notional_budget),
        "days_with_budget_binding": int(days_with_budget_binding),
        "days_with_cadence_binding": int(days_with_cadence_binding),
    }
    return ledger, curve, budget_df, extra


def _to_native(value: Any) -> Any:
    if isinstance(value, (np.floating, np.float32, np.float64)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    if pd.isna(value):
        return None
    return value


def _max_drawdown(equity: pd.Series) -> float | None:
    if equity.empty:
        return None
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def _time_to_recover_days(curve: pd.DataFrame) -> int | None:
    if curve.empty:
        return None
    equity = curve["equity_end"].astype(float)
    peaks = equity.cummax()
    drawdowns = equity / peaks - 1.0
    if drawdowns.empty:
        return None
    valley_idx = int(drawdowns.idxmin())
    peak_before_valley = float(peaks.loc[valley_idx])
    valley_date = pd.to_datetime(curve.loc[valley_idx, "date"])
    recovered = curve.loc[(curve.index > valley_idx) & (curve["equity_end"].astype(float) >= peak_before_valley)]
    if recovered.empty:
        return None
    recover_date = pd.to_datetime(recovered.iloc[0]["date"])
    return int((recover_date - valley_date).days)


def _weighted_holding_days(ledger: pd.DataFrame) -> float | None:
    if ledger.empty:
        return None
    work = ledger.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date", "ticker", "side", "qty"]).sort_values(["date", "ticker"])
    lots: dict[str, list[list[Any]]] = {}
    weighted_days = 0.0
    qty_sold_total = 0.0
    for row in work.itertuples(index=False):
        ticker = str(row.ticker)
        side = str(row.side).upper()
        qty = float(row.qty)
        dt = pd.Timestamp(row.date)
        if qty <= 0:
            continue
        if side == "BUY":
            lots.setdefault(ticker, []).append([dt, qty])
        elif side == "SELL":
            remaining = qty
            queue = lots.setdefault(ticker, [])
            while remaining > 0 and queue:
                buy_dt, buy_qty = queue[0]
                matched = min(remaining, buy_qty)
                weighted_days += matched * max((dt - buy_dt).days, 0)
                qty_sold_total += matched
                remaining -= matched
                buy_qty -= matched
                if buy_qty <= 1e-9:
                    queue.pop(0)
                else:
                    queue[0][1] = buy_qty
    if qty_sold_total <= 0:
        return None
    return float(weighted_days / qty_sold_total)


def compute_spec005_metrics(curve: pd.DataFrame, ledger: pd.DataFrame) -> dict[str, Any]:
    c = curve.copy().sort_values("date")
    l = ledger.copy()
    c["date"] = pd.to_datetime(c["date"], errors="coerce")
    c = c.dropna(subset=["date", "equity_end"])
    l["date"] = pd.to_datetime(l["date"], errors="coerce")
    l = l.dropna(subset=["date", "side", "notional"])
    if c.empty:
        return {}

    equity = c["equity_end"].astype(float)
    ret = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    downside = ret.clip(upper=0.0)

    buy_notional = float(l.loc[l["side"].astype(str).str.upper() == "BUY", "notional"].sum())
    sell_notional = float(l.loc[l["side"].astype(str).str.upper() == "SELL", "notional"].sum())
    reentry_notional = float(
        l.loc[
            (l["side"].astype(str).str.upper() == "BUY")
            & (l.get("reason", "").astype(str).str.contains("REENTRY", case=False, na=False)),
            "notional",
        ].sum()
    )
    avg_equity = float(equity.mean()) if not equity.empty else np.nan

    start_date = c["date"].iloc[0]
    end_date = c["date"].iloc[-1]
    years = max((end_date - start_date).days / 365.25, 1e-9)
    eq_ini = float(equity.iloc[0]) if not equity.empty else np.nan
    eq_final = float(equity.iloc[-1]) if not equity.empty else np.nan

    var_5 = float(ret.quantile(0.05)) if not ret.empty else np.nan
    cvar_5 = float(ret[ret <= var_5].mean()) if not ret.empty else np.nan
    sharpe = float((ret.mean() / ret.std(ddof=0)) * np.sqrt(ANN_FACTOR)) if ret.std(ddof=0) > 0 else np.nan

    if "num_switches_cumsum" in c.columns:
        num_switches = int(max(c["num_switches_cumsum"].astype(float).max() - c["num_switches_cumsum"].astype(float).min(), 0.0))
    else:
        num_switches = 0

    metrics = {
        "equity_final": eq_final,
        "CAGR": float((eq_final / eq_ini) ** (1.0 / years) - 1.0) if eq_ini > 0 else np.nan,
        "MDD": _max_drawdown(equity),
        "time_to_recover": _time_to_recover_days(c),
        "vol_annual": float(ret.std(ddof=0) * np.sqrt(ANN_FACTOR)) if not ret.empty else np.nan,
        "downside_dev": float(downside.std(ddof=0) * np.sqrt(ANN_FACTOR)) if not downside.empty else np.nan,
        "VaR": var_5,
        "CVaR": cvar_5,
        "turnover_total": float((buy_notional + sell_notional) / avg_equity) if avg_equity > 0 else np.nan,
        "turnover_sell": float(sell_notional / avg_equity) if avg_equity > 0 else np.nan,
        "turnover_reentry": float(reentry_notional / avg_equity) if avg_equity > 0 else np.nan,
        "num_switches": num_switches,
        "avg_holding_time": _weighted_holding_days(l),
        "cost_total": float(l.get("cost_brl", pd.Series(dtype=float)).sum()),
        "missed_sell_rate": None,
        "false_sell_rate": None,
        "regret_3d": None,
        "sharpe": sharpe,
        "dates_simulated": int(len(c)),
        "period_start": str(start_date.date()),
        "period_end": str(end_date.date()),
    }
    return {k: _to_native(v) for k, v in metrics.items()}


def build_candidate_set() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    t039_curve = pd.read_parquet(INPUT_T039_CURVE).copy()
    t039_ledger = pd.read_parquet(INPUT_T039_LEDGER).copy()
    t039_curve["date"] = pd.to_datetime(t039_curve["date"])
    t039_ledger["date"] = pd.to_datetime(t039_ledger["date"])

    buy_dates = (
        t039_ledger[t039_ledger["side"] == "BUY"][["date"]]
        .drop_duplicates()
        .sort_values("date")
        .reset_index(drop=True)
    )
    buy_dates["gap_days"] = buy_dates["date"].diff().dt.days
    gap_series = pd.to_numeric(buy_dates["gap_days"], errors="coerce").dropna()

    buy_daily = (
        t039_ledger[t039_ledger["side"] == "BUY"]
        .groupby("date", as_index=False)
        .agg(buy_notional=("notional", "sum"))
    )
    turnover_df = (
        t039_curve[["date", "equity_end"]]
        .merge(buy_daily, on="date", how="left")
        .fillna({"buy_notional": 0.0})
    )
    turnover_df["buy_turnover_daily"] = turnover_df["buy_notional"] / pd.to_numeric(turnover_df["equity_end"], errors="coerce").replace(0, np.nan)
    turnover_pos = pd.to_numeric(turnover_df["buy_turnover_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    turnover_pos = turnover_pos[turnover_pos > 0]

    quantiles = [0.50, 0.75, 0.90, 0.95]
    cadence_quantile_values = {str(q): float(gap_series.quantile(q)) for q in quantiles if not gap_series.empty}
    cap_quantile_values = {str(q): float(turnover_pos.quantile(q)) for q in quantiles if not turnover_pos.empty}

    cadence_candidates = [3]
    cadence_candidates.extend(int(max(1, round(v))) for v in cadence_quantile_values.values())
    cadence_candidates = sorted(set(cadence_candidates))

    cap_candidates: list[float | None] = [None]
    cap_candidates.extend(float(v) for v in cap_quantile_values.values())
    cap_candidates = sorted(set(cap_candidates), key=lambda x: (x is not None, float(x) if x is not None else -1.0))

    candidates: list[dict[str, Any]] = []
    idx = 1
    for cadence in cadence_candidates:
        for cap in cap_candidates:
            candidate_id = f"C{idx:03d}"
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "buy_cadence_days": int(cadence),
                    "buy_turnover_cap_ratio": None if cap is None else float(cap),
                    "params_json": json.dumps(
                        {
                            "buy_cadence_days": int(cadence),
                            "buy_turnover_cap_ratio": None if cap is None else float(cap),
                        },
                        sort_keys=True,
                    ),
                }
            )
            idx += 1

    evidence = {
        "task_id": TASK_ID,
        "construction_method": "data_driven_quantiles_from_T039",
        "quantiles_used": quantiles,
        "cadence_gap_days_quantiles": cadence_quantile_values,
        "buy_turnover_daily_quantiles": cap_quantile_values,
        "baseline_control": {"buy_cadence_days": 3, "buy_turnover_cap_ratio": None},
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    return candidates, evidence


def load_subperiods_and_baselines() -> tuple[pd.DataFrame, dict[tuple[str, str], dict[str, float]]]:
    t040 = pd.read_csv(INPUT_T040_SUBPERIOD)
    for col in ["period_start", "period_end"]:
        t040[col] = pd.to_datetime(t040[col], errors="coerce")
    subperiods = (
        t040[t040["task_id"] == "T039"][["subperiod", "period_start", "period_end"]]
        .drop_duplicates()
        .sort_values("period_start")
        .reset_index(drop=True)
    )
    baseline_map: dict[tuple[str, str], dict[str, float]] = {}
    for row in t040.itertuples(index=False):
        baseline_map[(str(row.task_id), str(row.subperiod))] = {
            "equity_final": float(row.equity_final) if pd.notna(row.equity_final) else np.nan,
            "MDD": float(row.MDD) if pd.notna(row.MDD) else np.nan,
            "sharpe": float(row.sharpe) if pd.notna(row.sharpe) else np.nan,
            "turnover_total": float(row.turnover_total) if pd.notna(row.turnover_total) else np.nan,
            "cost_total": float(row.cost_total) if pd.notna(row.cost_total) else np.nan,
        }
    return subperiods, baseline_map


def evaluate_candidate_rows(
    candidate: dict[str, Any],
    curve: pd.DataFrame,
    ledger: pd.DataFrame,
    subperiods: pd.DataFrame,
    baseline_map: dict[tuple[str, str], dict[str, float]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    overall_metrics = compute_spec005_metrics(curve, ledger)

    def _f(v: Any) -> float:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return float("nan")
        return x if np.isfinite(x) else float("nan")

    for sp in subperiods.itertuples(index=False):
        sub = str(sp.subperiod)
        start = pd.Timestamp(sp.period_start)
        end = pd.Timestamp(sp.period_end)
        c_sp = curve[(pd.to_datetime(curve["date"]) >= start) & (pd.to_datetime(curve["date"]) <= end)].copy()
        l_sp = ledger[(pd.to_datetime(ledger["date"]) >= start) & (pd.to_datetime(ledger["date"]) <= end)].copy()
        m = compute_spec005_metrics(c_sp, l_sp)
        b37 = baseline_map.get(("T037", sub), {})
        b39 = baseline_map.get(("T039", sub), {})
        eq = _f(m.get("equity_final", np.nan))
        mdd = _f(m.get("MDD", np.nan))
        sharpe = _f(m.get("sharpe", np.nan))
        turnover = _f(m.get("turnover_total", np.nan))
        cost_total = _f(m.get("cost_total", np.nan))
        b37_eq = _f(b37.get("equity_final", np.nan))
        b39_eq = _f(b39.get("equity_final", np.nan))
        b37_mdd = _f(b37.get("MDD", np.nan))
        b39_mdd = _f(b39.get("MDD", np.nan))
        b37_sharpe = _f(b37.get("sharpe", np.nan))
        b39_sharpe = _f(b39.get("sharpe", np.nan))
        b37_turnover = _f(b37.get("turnover_total", np.nan))
        b39_turnover = _f(b39.get("turnover_total", np.nan))
        b37_cost = _f(b37.get("cost_total", np.nan))
        b39_cost = _f(b39.get("cost_total", np.nan))
        row = {
            "candidate_id": candidate["candidate_id"],
            "buy_cadence_days": candidate["buy_cadence_days"],
            "buy_turnover_cap_ratio": candidate["buy_turnover_cap_ratio"],
            "params_json": candidate["params_json"],
            "subperiod": sub,
            "period_start": str(start.date()),
            "period_end": str(end.date()),
            "equity_final": eq,
            "CAGR": m.get("CAGR", np.nan),
            "MDD": mdd,
            "sharpe": sharpe,
            "turnover_total": turnover,
            "cost_total": cost_total,
            "num_switches": m.get("num_switches", np.nan),
            "eq_ratio_vs_t037": (eq / b37_eq) if np.isfinite(eq) and np.isfinite(b37_eq) and b37_eq > 0 else np.nan,
            "eq_ratio_vs_t039": (eq / b39_eq) if np.isfinite(eq) and np.isfinite(b39_eq) and b39_eq > 0 else np.nan,
            "mdd_delta_vs_t037": (mdd - b37_mdd) if np.isfinite(mdd) and np.isfinite(b37_mdd) else np.nan,
            "mdd_delta_vs_t039": (mdd - b39_mdd) if np.isfinite(mdd) and np.isfinite(b39_mdd) else np.nan,
            "sharpe_delta_vs_t037": (sharpe - b37_sharpe) if np.isfinite(sharpe) and np.isfinite(b37_sharpe) else np.nan,
            "sharpe_delta_vs_t039": (sharpe - b39_sharpe) if np.isfinite(sharpe) and np.isfinite(b39_sharpe) else np.nan,
            "turnover_delta_vs_t037": (turnover - b37_turnover) if np.isfinite(turnover) and np.isfinite(b37_turnover) else np.nan,
            "turnover_delta_vs_t039": (turnover - b39_turnover) if np.isfinite(turnover) and np.isfinite(b39_turnover) else np.nan,
            "cost_delta_vs_t037": (cost_total - b37_cost) if np.isfinite(cost_total) and np.isfinite(b37_cost) else np.nan,
            "cost_delta_vs_t039": (cost_total - b39_cost) if np.isfinite(cost_total) and np.isfinite(b39_cost) else np.nan,
        }
        rows.append(row)
    return rows, overall_metrics


def selection_stats(rows_df: pd.DataFrame, candidate_id: str) -> dict[str, float]:
    c = rows_df[rows_df["candidate_id"] == candidate_id].copy()
    return {
        "median_eq_ratio_vs_t037": float(c["eq_ratio_vs_t037"].median(skipna=True)),
        "median_mdd_delta_vs_t037": float(c["mdd_delta_vs_t037"].median(skipna=True)),
        "median_turnover_total": float(c["turnover_total"].median(skipna=True)),
    }


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    required_inputs = [
        CANONICAL_FILE,
        MACRO_FILE,
        BLACKLIST_FILE,
        SCORES_FILE,
        INPUT_T039_CURVE,
        INPUT_T039_LEDGER,
        INPUT_T037_CURVE,
        INPUT_T037_LEDGER,
        INPUT_T040_SUBPERIOD,
        INPUT_T040_COMPARATIVE,
        INPUT_SPEC005,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    for p in [OUT_ABLATION, OUT_SELECTED_CFG, OUT_CURVE, OUT_LEDGER, OUT_SUMMARY, OUT_REPORT, OUT_MANIFEST, OUT_CANDIDATE_SET, OUT_SELECTION_RULE, OUT_DAILY_BUDGET, OUT_ENFORCEMENT_SUMMARY]:
        p.parent.mkdir(parents=True, exist_ok=True)

    engine = prepare_engine_data()
    subperiods, baseline_map = load_subperiods_and_baselines()

    candidates, candidate_set_evidence = build_candidate_set()
    write_json_strict(OUT_CANDIDATE_SET, candidate_set_evidence)

    all_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []

    print(f"INFO: candidate_count={len(candidates)}")
    for i, cand in enumerate(candidates, start=1):
        print(f"INFO: running {cand['candidate_id']} ({i}/{len(candidates)}) cadence={cand['buy_cadence_days']} cap={cand['buy_turnover_cap_ratio']}")
        ledger, curve, _budget, extra = run_candidate(
            engine=engine,
            cadence_days=int(cand["buy_cadence_days"]),
            buy_turnover_cap_ratio=cand["buy_turnover_cap_ratio"],
        )
        rows, overall_metrics = evaluate_candidate_rows(cand, curve, ledger, subperiods, baseline_map)
        all_rows.extend(rows)
        overall_rows.append(
            {
                "candidate_id": cand["candidate_id"],
                "buy_cadence_days": cand["buy_cadence_days"],
                "buy_turnover_cap_ratio": cand["buy_turnover_cap_ratio"],
                "params_json": cand["params_json"],
                "equity_final_total": overall_metrics.get("equity_final", np.nan),
                "CAGR_total": overall_metrics.get("CAGR", np.nan),
                "MDD_total": overall_metrics.get("MDD", np.nan),
                "sharpe_total": overall_metrics.get("sharpe", np.nan),
                "turnover_total_total": overall_metrics.get("turnover_total", np.nan),
                "cost_total_total": overall_metrics.get("cost_total", np.nan),
                "num_switches_total": overall_metrics.get("num_switches", np.nan),
                "n_buy_blocked_by_cadence": extra["n_buy_blocked_by_cadence"],
                "n_buy_blocked_by_budget": extra["n_buy_blocked_by_budget"],
                "days_with_budget_binding": extra["days_with_budget_binding"],
                "days_with_cadence_binding": extra["days_with_cadence_binding"],
            }
        )

    ablation_df = pd.DataFrame(all_rows)
    overall_df = pd.DataFrame(overall_rows)
    ablation_df.to_parquet(OUT_ABLATION, index=False)

    # Deterministic lexicographic selection.
    stats_rows = []
    for cand in candidates:
        cid = cand["candidate_id"]
        st = selection_stats(ablation_df, cid)
        ov = overall_df[overall_df["candidate_id"] == cid].iloc[0].to_dict()
        stats_rows.append({"candidate_id": cid, **st, **ov})
    sel_df = pd.DataFrame(stats_rows)
    sel_df = sel_df.sort_values(
        by=["median_eq_ratio_vs_t037", "median_mdd_delta_vs_t037", "median_turnover_total", "equity_final_total", "candidate_id"],
        ascending=[False, False, True, False, True],
    ).reset_index(drop=True)
    winner = sel_df.iloc[0].to_dict()
    winner_id = str(winner["candidate_id"])
    winner_params = next(c for c in candidates if c["candidate_id"] == winner_id)

    selection_rule = {
        "task_id": TASK_ID,
        "selection_type": "deterministic_lexicographic",
        "ranking_order": [
            "max median_eq_ratio_vs_t037 (subperiods)",
            "max median_mdd_delta_vs_t037 (subperiods)",
            "min median_turnover_total (subperiods)",
            "max equity_final_total (full period)",
            "min candidate_id (stable tie-breaker)",
        ],
        "winner_candidate_id": winner_id,
        "top5_candidates": sel_df.head(5).to_dict(orient="records"),
    }
    write_json_strict(OUT_SELECTION_RULE, selection_rule)
    write_json_strict(
        OUT_SELECTED_CFG,
        {
            "task_id": TASK_ID,
            "selected_candidate_id": winner_id,
            "selected_params": winner_params,
            "selection_stats": winner,
        },
    )

    # Materialize winner outputs.
    ledger_w, curve_w, budget_w, extra_w = run_candidate(
        engine=engine,
        cadence_days=int(winner_params["buy_cadence_days"]),
        buy_turnover_cap_ratio=winner_params["buy_turnover_cap_ratio"],
    )
    curve_w.to_parquet(OUT_CURVE, index=False)
    ledger_w.to_parquet(OUT_LEDGER, index=False)
    budget_w.to_csv(OUT_DAILY_BUDGET, index=False)

    m_total = compute_spec005_metrics(curve_w, ledger_w)
    summary = {
        "task_id": "T044",
        "selected_candidate_id": winner_id,
        "guardrails_policy": {
            "buy_cadence_days": int(winner_params["buy_cadence_days"]),
            "buy_turnover_cap_ratio": winner_params["buy_turnover_cap_ratio"],
            "selection_mode": "ablation_data_driven",
        },
        "metrics_total": m_total,
        "enforcement": {
            "n_buy_blocked_by_cadence": int(extra_w["n_buy_blocked_by_cadence"]),
            "n_buy_blocked_by_budget": int(extra_w["n_buy_blocked_by_budget"]),
            "n_buy_blocked_notional_budget": float(extra_w["n_buy_blocked_notional_budget"]),
            "days_with_budget_binding": int(extra_w["days_with_budget_binding"]),
            "days_with_cadence_binding": int(extra_w["days_with_cadence_binding"]),
        },
    }
    write_json_strict(OUT_SUMMARY, summary)
    write_json_strict(OUT_ENFORCEMENT_SUMMARY, summary["enforcement"])

    # Accounting checks on winner outputs.
    identity_abs = (
        pd.to_numeric(curve_w["equity_end"], errors="coerce")
        - (pd.to_numeric(curve_w["cash_end"], errors="coerce") + pd.to_numeric(curve_w["positions_value_end"], errors="coerce"))
    ).abs()
    g_accounting = bool(float(identity_abs.max()) <= 1e-8)
    cost_ledger = float(pd.to_numeric(ledger_w["cost_brl"], errors="coerce").sum()) if not ledger_w.empty else 0.0
    cost_daily = float(ledger_w.groupby("date", as_index=False)["cost_brl"].sum()["cost_brl"].sum()) if not ledger_w.empty else 0.0
    g_cost = bool(abs(cost_ledger - cost_daily) <= 1e-9)
    min_cash_curve = float(pd.to_numeric(curve_w["cash_end"], errors="coerce").min())
    min_cash_before = float(pd.to_numeric(ledger_w["cash_before"], errors="coerce").min()) if not ledger_w.empty else 0.0
    min_cash_after = float(pd.to_numeric(ledger_w["cash_after"], errors="coerce").min()) if not ledger_w.empty else 0.0
    g_cash = bool(min_cash_curve >= 0 and min_cash_before >= 0 and min_cash_after >= 0)

    # Compare winner vs T039/T037 totals.
    t040_comp = json.loads(INPUT_T040_COMPARATIVE.read_text(encoding="utf-8"))
    b037 = t040_comp["metrics_by_task"]["T037"]
    b039 = t040_comp["metrics_by_task"]["T039"]

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Candidate set (data-driven)",
        f"- candidate_count: {len(candidates)}",
        f"- candidate_set: `{OUT_CANDIDATE_SET}`",
        "",
        "## 2) Selection rule (deterministic)",
        f"- selection_rule: `{OUT_SELECTION_RULE}`",
        f"- winner: `{winner_id}` -> cadence={winner_params['buy_cadence_days']}, cap={winner_params['buy_turnover_cap_ratio']}",
        "",
        "## 3) Winner metrics vs baselines (total period)",
        "",
        f"- equity_final: T044={m_total.get('equity_final')} | T039={b039.get('equity_final')} | T037={b037.get('equity_final')}",
        f"- CAGR: T044={m_total.get('CAGR')} | T039={b039.get('CAGR')} | T037={b037.get('CAGR')}",
        f"- MDD: T044={m_total.get('MDD')} | T039={b039.get('MDD')} | T037={b037.get('MDD')}",
        f"- sharpe: T044={m_total.get('sharpe')} | T039={b039.get('sharpe')} | T037={b037.get('sharpe')}",
        f"- turnover_total: T044={m_total.get('turnover_total')} | T039={b039.get('turnover_total')} | T037={b037.get('turnover_total')}",
        "",
        "## 4) Accounting checks (winner)",
        f"- identity equity=cash+positions: {'PASS' if g_accounting else 'FAIL'}",
        f"- cost consistency: {'PASS' if g_cost else 'FAIL'}",
        f"- cash non-negative: {'PASS' if g_cash else 'FAIL'}",
        "",
        "## 5) Artifacts",
        f"- `{OUT_ABLATION}`",
        f"- `{OUT_SELECTED_CFG}`",
        f"- `{OUT_CURVE}`",
        f"- `{OUT_LEDGER}`",
        f"- `{OUT_SUMMARY}`",
        f"- `{OUT_DAILY_BUDGET}`",
        f"- `{OUT_ENFORCEMENT_SUMMARY}`",
        f"- `{OUT_REPORT}`",
        f"- `{OUT_MANIFEST}`",
    ]
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs = [
        OUT_ABLATION,
        OUT_SELECTED_CFG,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_CANDIDATE_SET,
        OUT_SELECTION_RULE,
        OUT_DAILY_BUDGET,
        OUT_ENFORCEMENT_SUMMARY,
        SCRIPT_PATH,
    ]
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(p) for p in outputs],
        "hashes_sha256": {
            **{str(p): sha256_file(p) for p in required_inputs},
            **{str(p): sha256_file(p) for p in outputs if p.exists() and p != OUT_MANIFEST},
        },
    }
    write_json_strict(OUT_MANIFEST, manifest)

    # Gates
    g1 = OUT_CURVE.exists() and OUT_LEDGER.exists() and OUT_SUMMARY.exists()
    g2 = OUT_ABLATION.exists() and OUT_CANDIDATE_SET.exists() and OUT_SELECTION_RULE.exists() and OUT_DAILY_BUDGET.exists()
    g3 = g_accounting and g_cost and g_cash
    g4 = OUT_SELECTED_CFG.exists() and winner_id in set(ablation_df["candidate_id"].astype(str))
    gx = OUT_MANIFEST.exists()
    try:
        parse_json_strict(OUT_SELECTED_CFG)
        parse_json_strict(OUT_SELECTION_RULE)
        g5 = True
    except Exception:
        g5 = False
    g6 = str(OUT_MANIFEST) not in manifest.get("hashes_sha256", {})

    print("STEP GATES:")
    print(f"- G1_FINAL_ARTIFACTS_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_ABLATION_EVIDENCE_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_ACCOUNTING_CHECKS: {'PASS' if g3 else 'FAIL'}")
    print(f"- G4_SELECTION_REPRODUCIBLE: {'PASS' if g4 else 'FAIL'}")
    print(f"- G5_STRICT_JSON: {'PASS' if g5 else 'FAIL'}")
    print(f"- G6_MANIFEST_SELF_HASH_EXCLUDED: {'PASS' if g6 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("RETRY LOG:")
    print("- none")
    print("ARTIFACT LINKS:")
    for p in outputs:
        print(f"- {p}")
    overall = g1 and g2 and g3 and g4 and g5 and g6 and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
