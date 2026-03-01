#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T068-RALLY-PROTECTION-ABLATION-V1"
BASE_CAPITAL = 100000.0
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

SCRIPT_BASE = ROOT / "scripts/t063_market_slope_reentry_ablation.py"
SCRIPT_REF_T067 = ROOT / "scripts/t067_aggressive_allocation_ablation.py"

INPUT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
INPUT_BLACKLIST = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
INPUT_SCORES = ROOT / "src/data_engine/features/T037_M3_SCORES_DAILY.parquet"

INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T067_CURVE = ROOT / "src/data_engine/portfolio/T067_PORTFOLIO_CURVE_AGGRESSIVE.parquet"
INPUT_T063_CURVE = ROOT / "src/data_engine/portfolio/T063_PORTFOLIO_CURVE_REENTRY_FIX_V2.parquet"
INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"

INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_T067_SUMMARY = ROOT / "src/data_engine/portfolio/T067_BASELINE_SUMMARY_AGGRESSIVE.json"
INPUT_T063_SUMMARY = ROOT / "src/data_engine/portfolio/T063_BASELINE_SUMMARY_REENTRY_FIX_V2.json"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"

OUT_ABLATION = ROOT / "src/data_engine/portfolio/T068_RALLY_PROTECTION_ABLATION_RESULTS.parquet"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T068_RALLY_PROTECTION_SELECTED_CONFIG.json"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T068_PORTFOLIO_CURVE_RALLY_PROTECTION.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T068_PORTFOLIO_LEDGER_RALLY_PROTECTION.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T068_BASELINE_SUMMARY_RALLY_PROTECTION.json"

OUT_HTML = ROOT / "outputs/plots/T068_STATE3_PHASE4B_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T068-RALLY-PROTECTION-ABLATION-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T068-RALLY-PROTECTION-ABLATION-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T068-RALLY-PROTECTION-ABLATION-V1_evidence"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_FEASIBILITY = OUT_EVIDENCE_DIR / "feasibility_snapshot.json"
OUT_METRICS_SNAPSHOT = OUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUT_PLOT_INVENTORY = OUT_EVIDENCE_DIR / "plot_inventory.json"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-01T13:30:00Z | STRATEGY: T068-RALLY-PROTECTION-ABLATION-V1 EXEC. "
    "Artefatos: outputs/plots/T068_STATE3_PHASE4B_COMPARATIVE.html; "
    "outputs/governanca/T068-RALLY-PROTECTION-ABLATION-V1_report.md; "
    "outputs/governanca/T068-RALLY-PROTECTION-ABLATION-V1_manifest.json; "
    "src/data_engine/portfolio/T068_RALLY_PROTECTION_SELECTED_CONFIG.json"
)


SLOPE_WINDOW = 30
CADENCE_DAYS = 10
BUY_TURNOVER_CAP_RATIO: float | None = None
IN_HYST_GRID = [2, 3, 4]
OUT_HYST_GRID = [4, 6, 8, 10]
TREND_WINDOW_GRID = [150, 200]
MODE_A = "ASYM_HYST"
MODE_B = "HYBRID_TREND"

THRESHOLDS = {
    "MDD_total_min": -0.30,
    "excess_return_2023plus_vs_t044_min": 0.0,
}
SELECTION_ORDER = [
    "equity_final_total DESC",
    "excess_return_rally_vs_t044 DESC",
    "Sharpe_total DESC",
    "turnover_total ASC",
    "candidate_id ASC",
]


def _load_base_module():
    spec = importlib.util.spec_from_file_location("t063_base_module", SCRIPT_BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar script base: {SCRIPT_BASE}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if pd.isna(obj):
        return None
    return obj


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def parse_json_strict(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    return json.loads(
        txt, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid constant: {x}"))
    )


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
    expected = len((line.rstrip("\n") + "\n").encode("utf-8"))
    return delta == expected and text.endswith(line.rstrip("\n") + "\n")


def normalize_to_base(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return BASE_CAPITAL * (s / float(s.iloc[0]))


def compute_drawdown(equity_norm: pd.Series) -> pd.Series:
    s = pd.to_numeric(equity_norm, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def benchmark_metrics(series: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float((s / s.cummax() - 1.0).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {"equity_final": float(s.iloc[-1]), "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def participation_metrics_safe(curve: pd.DataFrame) -> dict[str, float]:
    c = curve.copy()
    exposure = pd.to_numeric(c.get("exposure", pd.Series(np.nan, index=c.index)), errors="coerce")
    equity = pd.to_numeric(c.get("equity_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash = pd.to_numeric(c.get("cash_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash_weight = (cash / equity.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    regime = pd.to_numeric(c.get("regime_defensivo", pd.Series(np.nan, index=c.index)), errors="coerce")
    return {
        "time_in_market_frac": float((exposure > 0).mean()) if len(exposure) else np.nan,
        "avg_exposure": float(exposure.mean()) if len(exposure.dropna()) else np.nan,
        "days_cash_ge_090_frac": float((cash_weight >= 0.90).mean()) if len(cash_weight) else np.nan,
        "days_defensive_frac": float(regime.fillna(0).astype(bool).mean()) if len(regime) else np.nan,
    }


def find_true_intervals(mask: pd.Series, dates: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = None
    prev = None
    for m, dt in zip(mask.tolist(), dates.tolist()):
        if m and start is None:
            start = dt
        if not m and start is not None:
            intervals.append((start, prev if prev is not None else dt))
            start = None
        prev = dt
    if start is not None and prev is not None:
        intervals.append((start, prev))
    return intervals


def get_metric(d: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        v = d.get(key)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if np.isfinite(fv):
            return fv
    return None


def subperiod_return(curve: pd.DataFrame, start: str, end: str | None = None) -> float:
    c = curve.copy()
    c["date"] = pd.to_datetime(c["date"], errors="coerce").dt.normalize()
    c = c.sort_values("date").reset_index(drop=True)
    c = c[c["date"] >= pd.Timestamp(start)].copy()
    if end is not None:
        c = c[c["date"] <= pd.Timestamp(end)].copy()
    if len(c) < 2:
        return float("nan")
    eq = pd.to_numeric(c["equity_end"], errors="coerce").astype(float)
    if not np.isfinite(eq.iloc[0]) or eq.iloc[0] <= 0:
        return float("nan")
    return float(eq.iloc[-1] / eq.iloc[0] - 1.0)


def run_candidate_t068(
    base: Any,
    engine: Any,
    mode: str,
    in_hyst: int,
    out_hyst: int,
    trend_window: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    px_wide = engine.px_wide
    z_wide = engine.z_wide
    macro_day = engine.macro_day
    scores_by_day = engine.scores_by_day
    sim_dates = engine.sim_dates
    market_mu_slope = base.compute_market_mu_slope(engine, slope_window=SLOPE_WINDOW)

    ibov_series = pd.to_numeric(macro_day["ibov_close"], errors="coerce").astype(float)
    if mode == MODE_B:
        if trend_window is None:
            raise ValueError("trend_window obrigatorio no modo HYBRID_TREND")
        min_periods = max(20, int(trend_window // 4))
        ibov_ma = ibov_series.rolling(window=int(trend_window), min_periods=min_periods).mean().ffill().bfill()
    else:
        ibov_ma = pd.Series(np.nan, index=ibov_series.index)

    cash = float(base.INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    ledger_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []

    trend_down = False
    down_streak = 0
    up_streak = 0
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
            fee = notional * base.ORDER_COST_RATE
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
            blocked_reentry.add(ticker)

        cdi_log = float(m["cdi_log_daily"]) if pd.notna(m["cdi_log_daily"]) else 0.0
        cdi_daily = np.exp(cdi_log) - 1.0
        cash_before_cdi = cash
        cash *= 1.0 + cdi_daily
        cdi_credit = cash - cash_before_cdi

        pos_val_mid = base.positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        for ticker, qty in list(positions.items()):
            if qty <= 0:
                continue
            px = float(px_row.get(ticker, np.nan))
            if not np.isfinite(px) or px <= 0:
                continue
            cur_val = qty * px
            cur_pct = cur_val / equity_mid if equity_mid > 0 else 0.0
            if cur_pct <= base.MAX_PCT:
                continue
            target_val = base.TARGET_PCT * equity_mid
            excess_val = max(0.0, cur_val - target_val)
            qty_sell = int(min(qty, math.floor(excess_val / px)))
            if qty_sell <= 0:
                continue
            notional = qty_sell * px
            net = notional * (1.0 - base.ORDER_COST_RATE)
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

        pos_val_mid = base.positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        prev_regime = bool(trend_down)
        slope = float(market_mu_slope.loc[d]) if d in market_mu_slope.index else 0.0
        ma_val = float(ibov_ma.loc[d]) if d in ibov_ma.index else np.nan
        below_ma = bool(np.isfinite(ma_val) and ibov < ma_val)
        above_ma = bool(np.isfinite(ma_val) and ibov > ma_val)

        if not trend_down:
            if mode == MODE_B:
                enter_cond = (slope < 0.0) and below_ma
            else:
                enter_cond = slope < 0.0
            down_streak = down_streak + 1 if enter_cond else 0
            if down_streak >= out_hyst:
                trend_down = True
                down_streak = 0
                up_streak = 0
        else:
            if mode == MODE_B:
                recover_cond = (slope > 0.0) or above_ma
            else:
                recover_cond = slope > 0.0
            up_streak = up_streak + 1 if recover_cond else 0
            if up_streak >= in_hyst:
                trend_down = False
                up_streak = 0
                down_streak = 0

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
            band = base.band_from_z(z0)
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
                    sell_pct = base.score_to_sell_pct(int(c["score"]))
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

        buy_day = day_idx % CADENCE_DAYS == 0
        daily_buy_notional = 0.0
        buy_budget = float("inf")
        blocked_budget_events_day = 0
        blocked_notional_day = 0.0

        if buy_day and d in scores_by_day and not regime_defensivo:
            day_scores = scores_by_day[d]
            top_candidates = day_scores[day_scores["m3_rank"] <= base.TOP_N].sort_values("m3_rank")
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
                target_val = base.TARGET_PCT * equity_mid
                if cur_val >= target_val:
                    continue
                buy_val = max(0.0, target_val - cur_val)
                qty_buy = int(math.floor(buy_val / px))
                if qty_buy <= 0:
                    continue
                notional = qty_buy * px
                fee = notional * base.ORDER_COST_RATE
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
                ledger_rows.append(
                    {
                        "date": d,
                        "ticker": ticker,
                        "side": "BUY",
                        "reason": "M3_TOPN",
                        "qty": qty_buy,
                        "price": px,
                        "notional": notional,
                        "net_notional": notional,
                        "cost_brl": fee,
                        "cash_before": cash_before,
                        "cash_after": cash,
                        "blocked_by_guardrail": False,
                    }
                )
        elif buy_day and d in scores_by_day and regime_defensivo:
            blocked_buy_events_regime += 1

        pos_val_end = base.positions_value(positions, px_row)
        equity_end = cash + pos_val_end
        exposure = pos_val_end / equity_end if equity_end > 0 else 0.0
        benchmark = base.INITIAL_CAPITAL * (ibov / engine.ibov_base) if engine.ibov_base > 0 else np.nan
        n_positions = sum(1 for q in positions.values() if q > 0)

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
                "regime_defensivo": bool(regime_defensivo),
                "market_mu_slope": float(slope),
                "ibov_trend_ma": float(ma_val) if np.isfinite(ma_val) else np.nan,
                "num_switches_cumsum": int(num_switches),
                "n_blocked_reentry": int(len(blocked_reentry)),
                "blocked_buy_events_regime_cumsum": int(blocked_buy_events_regime),
                "n_reentry_blocks_cumsum": int(n_reentry_blocks),
                "blocked_buy_notional_day": float(blocked_notional_day),
                "n_buy_blocked_budget_day": int(blocked_budget_events_day),
                "buy_cadence_days_effective": int(CADENCE_DAYS),
                "buy_turnover_cap_ratio_effective": np.nan,
                "mode": mode,
                "trend_window_effective": int(trend_window) if trend_window is not None else np.nan,
            }
        )

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


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    gates: dict[str, str] = {}
    retry_log: list[str] = []

    required_inputs = [
        INPUT_CANONICAL,
        INPUT_MACRO,
        INPUT_BLACKLIST,
        INPUT_SCORES,
        INPUT_T044_CURVE,
        INPUT_T067_CURVE,
        INPUT_T063_CURVE,
        INPUT_T037_CURVE,
        INPUT_T044_SUMMARY,
        INPUT_T067_SUMMARY,
        INPUT_T063_SUMMARY,
        INPUT_T037_SUMMARY,
        SCRIPT_BASE,
        SCRIPT_REF_T067,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        gates["G0_INPUTS_PRESENT"] = "FAIL"
        print("STEP GATES:")
        for k, v in gates.items():
            print(f"- {k}: {v} (missing: {', '.join(missing)})")
        print("RETRY LOG:")
        print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUT_ABLATION.parent.mkdir(parents=True, exist_ok=True)
    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    base = _load_base_module()
    engine = base.prepare_engine_data()

    t044_curve = pd.read_parquet(INPUT_T044_CURVE).copy()
    t067_curve = pd.read_parquet(INPUT_T067_CURVE).copy()
    t063_curve = pd.read_parquet(INPUT_T063_CURVE).copy()
    t037_curve = pd.read_parquet(INPUT_T037_CURVE).copy()
    macro = pd.read_parquet(INPUT_MACRO).copy()

    t044_summary = parse_json_strict(INPUT_T044_SUMMARY)
    t067_summary = parse_json_strict(INPUT_T067_SUMMARY)
    t063_summary = parse_json_strict(INPUT_T063_SUMMARY)
    t037_summary = parse_json_strict(INPUT_T037_SUMMARY)

    gates["G0_INPUTS_PRESENT"] = "PASS"

    t044_ret_2023 = subperiod_return(t044_curve, "2023-01-01")
    t044_ret_rally = subperiod_return(t044_curve, "2020-06-01", "2021-07-31")
    if not np.isfinite(t044_ret_2023) or not np.isfinite(t044_ret_rally):
        gates["G1_BENCHMARK_REF_PRESENT"] = "FAIL"
        print("STEP GATES:")
        for k, v in gates.items():
            print(f"- {k}: {v}")
        print("RETRY LOG:")
        print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1
    gates["G1_BENCHMARK_REF_PRESENT"] = "PASS"

    candidates: list[dict[str, Any]] = []
    for ih in IN_HYST_GRID:
        for oh in OUT_HYST_GRID:
            candidates.append(
                {
                    "candidate_id": f"A_IN{ih}_OUT{oh}",
                    "mode": MODE_A,
                    "in_hyst_days": int(ih),
                    "out_hyst_days": int(oh),
                    "trend_window": None,
                }
            )
    for ih in IN_HYST_GRID:
        for oh in OUT_HYST_GRID:
            for tw in TREND_WINDOW_GRID:
                candidates.append(
                    {
                        "candidate_id": f"B_TW{tw}_IN{ih}_OUT{oh}",
                        "mode": MODE_B,
                        "in_hyst_days": int(ih),
                        "out_hyst_days": int(oh),
                        "trend_window": int(tw),
                    }
                )
    write_json_strict(
        OUT_CANDIDATE_SET,
        {
            "task_id": TASK_ID,
            "fixed": {
                "slope_window": SLOPE_WINDOW,
                "cadence_days": CADENCE_DAYS,
                "buy_turnover_cap_ratio": BUY_TURNOVER_CAP_RATIO,
            },
            "grid": {
                "mode": [MODE_A, MODE_B],
                "in_hyst_days": IN_HYST_GRID,
                "out_hyst_days": OUT_HYST_GRID,
                "trend_window_hybrid_only": TREND_WINDOW_GRID,
            },
            "candidate_count": len(candidates),
            "candidates": candidates,
        },
    )

    rows: list[dict[str, Any]] = []
    feasible_rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_key: tuple[Any, ...] | None = None

    for cand in candidates:
        ledger, curve, extra = run_candidate_t068(
            base=base,
            engine=engine,
            mode=str(cand["mode"]),
            in_hyst=int(cand["in_hyst_days"]),
            out_hyst=int(cand["out_hyst_days"]),
            trend_window=cand["trend_window"],
        )
        m = base.compute_metrics(curve["equity_end"])
        p = participation_metrics_safe(curve)
        t_total = base.turnover_total(ledger, curve)
        t_reentry = base.subperiod_time_in_market(curve, base.REENTRY_SUBPERIOD_START, base.REENTRY_SUBPERIOD_END)
        eq_final = float(pd.to_numeric(curve["equity_end"], errors="coerce").astype(float).iloc[-1])
        ret_2023 = subperiod_return(curve, "2023-01-01")
        ret_rally = subperiod_return(curve, "2020-06-01", "2021-07-31")
        excess_2023 = float(ret_2023 - t044_ret_2023) if np.isfinite(ret_2023) else float("nan")
        excess_rally = float(ret_rally - t044_ret_rally) if np.isfinite(ret_rally) else float("nan")

        row = {
            "candidate_id": cand["candidate_id"],
            "mode": cand["mode"],
            "in_hyst_days": int(cand["in_hyst_days"]),
            "out_hyst_days": int(cand["out_hyst_days"]),
            "trend_window": cand["trend_window"],
            "cadence_days": CADENCE_DAYS,
            "buy_turnover_cap_ratio": BUY_TURNOVER_CAP_RATIO,
            "equity_final_total": eq_final,
            "CAGR_total": float(m["cagr"]),
            "MDD_total": float(m["mdd"]),
            "Sharpe_total": float(m["sharpe"]),
            "turnover_total": float(t_total),
            "time_in_market_frac": float(p["time_in_market_frac"]),
            "avg_exposure": float(p["avg_exposure"]),
            "days_cash_ge_090_frac": float(p["days_cash_ge_090_frac"]),
            "days_defensive_frac": float(p["days_defensive_frac"]),
            "reentry_subperiod_time_in_market": float(t_reentry),
            "num_switches": int(extra.get("num_switches", 0)),
            "return_2023plus": float(ret_2023),
            "excess_return_2023plus_vs_t044": float(excess_2023),
            "return_rally_2020_06_2021_07": float(ret_rally),
            "excess_return_rally_vs_t044": float(excess_rally),
        }
        rows.append(row)

        feasible = (
            np.isfinite(row["MDD_total"])
            and row["MDD_total"] >= THRESHOLDS["MDD_total_min"]
            and np.isfinite(row["excess_return_2023plus_vs_t044"])
            and row["excess_return_2023plus_vs_t044"] >= THRESHOLDS["excess_return_2023plus_vs_t044_min"]
        )
        if feasible:
            feasible_rows.append(row)
            key = (
                -row["equity_final_total"],
                -row["excess_return_rally_vs_t044"],
                -row["Sharpe_total"],
                row["turnover_total"],
                row["candidate_id"],
            )
            if best_key is None or key < best_key:
                best_key = key
                best = {"cfg": cand, "row": row, "curve": curve, "ledger": ledger}

    ablation_df = pd.DataFrame(rows).sort_values(
        ["equity_final_total", "excess_return_rally_vs_t044", "Sharpe_total", "turnover_total"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    ablation_df.to_parquet(OUT_ABLATION, index=False)
    gates["G2_ABLATION_RESULTS_PRESENT"] = "PASS"

    write_json_strict(
        OUT_FEASIBILITY,
        {
            "task_id": TASK_ID,
            "thresholds": THRESHOLDS,
            "selection_order": SELECTION_ORDER,
            "total_candidates": len(candidates),
            "feasible_count": len(feasible_rows),
            "feasible_candidate_ids": [r["candidate_id"] for r in feasible_rows],
            "t044_ref": {
                "return_2023plus": float(t044_ret_2023),
                "return_rally_2020_06_2021_07": float(t044_ret_rally),
            },
        },
    )

    if best is None:
        gates["G3_FEASIBLE_NONEMPTY"] = "FAIL"
        OUT_REPORT.write_text(
            "\n".join(
                [
                    f"# {TASK_ID} Report",
                    "",
                    "## Resultado",
                    f"- feasible_count: 0 / {len(candidates)}",
                    "- Nenhum candidato satisfaz os hard constraints de MDD e excesso 2023+.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        gates["G3_FEASIBLE_NONEMPTY"] = "PASS"
        cfg = best["cfg"]
        row = best["row"]
        win_curve = best["curve"].copy()
        win_ledger = best["ledger"].copy()

        write_json_strict(
            OUT_SELECTED_CFG,
            {
                "task_id": TASK_ID,
                "selected_candidate_id": cfg["candidate_id"],
                "mode": cfg["mode"],
                "cadence_days": CADENCE_DAYS,
                "buy_turnover_cap_ratio": BUY_TURNOVER_CAP_RATIO,
                "market_slope_window": SLOPE_WINDOW,
                "in_hyst_days": int(cfg["in_hyst_days"]),
                "out_hyst_days": int(cfg["out_hyst_days"]),
                "trend_window": cfg["trend_window"],
                "thresholds": THRESHOLDS,
                "selection_order": SELECTION_ORDER,
            },
        )
        win_curve.to_parquet(OUT_CURVE, index=False)
        win_ledger.to_parquet(OUT_LEDGER, index=False)
        write_json_strict(
            OUT_SUMMARY,
            {
                "task_id": TASK_ID,
                "selected_candidate_id": cfg["candidate_id"],
                "mode": cfg["mode"],
                "equity_final": float(row["equity_final_total"]),
                "cagr": float(row["CAGR_total"]),
                "mdd": float(row["MDD_total"]),
                "sharpe": float(row["Sharpe_total"]),
                "turnover_total": float(row["turnover_total"]),
                "time_in_market_frac": float(row["time_in_market_frac"]),
                "avg_exposure": float(row["avg_exposure"]),
                "days_cash_ge_090_frac": float(row["days_cash_ge_090_frac"]),
                "days_defensive_frac": float(row["days_defensive_frac"]),
                "num_switches": int(row["num_switches"]),
                "return_2023plus": float(row["return_2023plus"]),
                "excess_return_2023plus_vs_t044": float(row["excess_return_2023plus_vs_t044"]),
                "return_rally_2020_06_2021_07": float(row["return_rally_2020_06_2021_07"]),
                "excess_return_rally_vs_t044": float(row["excess_return_rally_vs_t044"]),
            },
        )
        write_json_strict(
            OUT_SELECTION_RULE,
            {
                "task_id": TASK_ID,
                "constraints": THRESHOLDS,
                "selection_order": SELECTION_ORDER,
                "selected_candidate_id": cfg["candidate_id"],
            },
        )
        gates["G4_WINNER_ARTIFACTS_PRESENT"] = "PASS"

        for df in [win_curve, t044_curve, t067_curve, t063_curve, t037_curve, macro]:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        common_dates = (
            set(win_curve["date"].dropna())
            & set(t044_curve["date"].dropna())
            & set(t067_curve["date"].dropna())
            & set(t063_curve["date"].dropna())
            & set(t037_curve["date"].dropna())
            & set(macro["date"].dropna())
        )
        common_dates = sorted(pd.to_datetime(list(common_dates)))
        if len(common_dates) < 30:
            raise RuntimeError("intersecao de datas insuficiente para plotly")

        def align_curve(df: pd.DataFrame) -> pd.DataFrame:
            out = df[df["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)
            out["equity_norm"] = normalize_to_base(out["equity_end"])
            return out

        wina = align_curve(win_curve)
        t044a = align_curve(t044_curve)
        t067a = align_curve(t067_curve)
        t063a = align_curve(t063_curve)
        t037a = align_curve(t037_curve)
        macroa = macro[macro["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)

        cdi_source = "cdi_log_daily"
        if "cdi_log_daily" in macroa.columns:
            cdi_log = pd.to_numeric(macroa["cdi_log_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            cdi_growth = np.exp(np.cumsum(cdi_log.to_numpy(dtype=float)))
        elif "cdi_daily" in macroa.columns:
            cdi_source = "cdi_daily"
            cdi_daily = pd.to_numeric(macroa["cdi_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            cdi_growth = (1.0 + cdi_daily.to_numpy(dtype=float)).cumprod()
        elif "cdi_rate_daily" in macroa.columns:
            cdi_source = "cdi_rate_daily"
            cdi_daily = pd.to_numeric(macroa["cdi_rate_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            cdi_growth = (1.0 + cdi_daily.to_numpy(dtype=float)).cumprod()
        else:
            raise RuntimeError("macro sem cdi_log_daily/cdi_daily/cdi_rate_daily")
        cdi_rebased = BASE_CAPITAL * (cdi_growth / float(cdi_growth[0]))

        if "ibov_close" not in macroa.columns:
            raise RuntimeError("macro sem ibov_close")
        ibov_close = pd.to_numeric(macroa["ibov_close"], errors="coerce").ffill().bfill().astype(float)
        ibov_rebased = normalize_to_base(ibov_close)

        dd68 = compute_drawdown(wina["equity_norm"])
        dd44 = compute_drawdown(t044a["equity_norm"])
        dd67 = compute_drawdown(t067a["equity_norm"])
        dd63 = compute_drawdown(t063a["equity_norm"])
        dd37 = compute_drawdown(t037a["equity_norm"])

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.55, 0.25, 0.20],
            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
            subplot_titles=[
                "Equity Normalizada (Base R$100k): T068 vs T044 vs T067 vs T063 vs T037 + CDI + IBOV",
                "Drawdown Overlay: T068 vs T044 vs T067 vs T063 vs T037",
                "Tabela de Metricas",
            ],
        )
        fig.add_trace(go.Scatter(x=wina["date"], y=wina["equity_norm"], mode="lines", name="T068 Rally Protection", line=dict(color="#2ca02c", width=2.8)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t044a["date"], y=t044a["equity_norm"], mode="lines", name="T044 Winner Phase2", line=dict(color="#d62728", dash="dash", width=2.0)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t067a["date"], y=t067a["equity_norm"], mode="lines", name="T067 Aggressive", line=dict(color="#ff7f0e", dash="dot", width=1.9)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t063a["date"], y=t063a["equity_norm"], mode="lines", name="T063 Reentry Fix", line=dict(color="#9467bd", dash="dot", width=1.9)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t037a["date"], y=t037a["equity_norm"], mode="lines", name="T037 Baseline", line=dict(color="#1f77b4", dash="dot", width=1.9)), row=1, col=1)
        fig.add_trace(go.Scatter(x=wina["date"], y=cdi_rebased, mode="lines", name="CDI Acumulado", line=dict(color="#7f7f7f", width=1.7)), row=1, col=1)
        fig.add_trace(go.Scatter(x=wina["date"], y=ibov_rebased, mode="lines", name="Ibovespa ^BVSP", line=dict(color="#111111", width=1.7)), row=1, col=1)

        fig.add_trace(go.Scatter(x=wina["date"], y=dd68, mode="lines", name="DD T068", line=dict(color="#2ca02c", width=1.9)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t044a["date"], y=dd44, mode="lines", name="DD T044", line=dict(color="#d62728", dash="dash", width=1.6)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t067a["date"], y=dd67, mode="lines", name="DD T067", line=dict(color="#ff7f0e", dash="dot", width=1.6)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t063a["date"], y=dd63, mode="lines", name="DD T063", line=dict(color="#9467bd", dash="dot", width=1.6)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t037a["date"], y=dd37, mode="lines", name="DD T037", line=dict(color="#1f77b4", dash="dot", width=1.6)), row=2, col=1)

        for df, color in [(wina, "rgba(44, 160, 44, 0.08)"), (t044a, "rgba(214, 39, 40, 0.06)")]:
            regime = pd.to_numeric(df.get("regime_defensivo", 0), errors="coerce").fillna(0).astype(bool)
            for x0, x1 in find_true_intervals(regime, df["date"]):
                fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=1, col=1)
                fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=2, col=1)

        pm68 = participation_metrics_safe(wina)
        pm44 = participation_metrics_safe(t044a)
        pm67 = participation_metrics_safe(t067a)
        pm63 = participation_metrics_safe(t063a)
        pm37 = participation_metrics_safe(t037a)
        bm_cdi = benchmark_metrics(pd.Series(cdi_rebased))
        bm_ibov = benchmark_metrics(pd.Series(ibov_rebased))
        m44 = t044_summary.get("metrics_total", {})
        m67 = t067_summary
        m63 = t063_summary
        m37 = t037_summary

        table_rows = ["T068", "T044", "T067", "T063", "T037", "CDI", "IBOV"]
        table_equity = [
            float(row["equity_final_total"]),
            get_metric(m44, ["equity_final"]),
            get_metric(m67, ["equity_final"]),
            get_metric(m63, ["equity_final"]),
            get_metric(m37, ["equity_final"]),
            bm_cdi["equity_final"],
            bm_ibov["equity_final"],
        ]
        table_cagr = [
            float(row["CAGR_total"]),
            get_metric(m44, ["CAGR", "cagr"]),
            get_metric(m67, ["cagr", "CAGR"]),
            get_metric(m63, ["cagr", "CAGR"]),
            get_metric(m37, ["cagr", "CAGR"]),
            bm_cdi["cagr"],
            bm_ibov["cagr"],
        ]
        table_mdd = [
            float(row["MDD_total"]),
            get_metric(m44, ["MDD", "mdd"]),
            get_metric(m67, ["mdd", "MDD"]),
            get_metric(m63, ["mdd", "MDD"]),
            get_metric(m37, ["mdd", "MDD"]),
            bm_cdi["mdd"],
            bm_ibov["mdd"],
        ]
        table_sharpe = [
            float(row["Sharpe_total"]),
            get_metric(m44, ["sharpe"]),
            get_metric(m67, ["sharpe"]),
            get_metric(m63, ["sharpe"]),
            get_metric(m37, ["sharpe"]),
            bm_cdi["sharpe"],
            bm_ibov["sharpe"],
        ]
        table_turnover = [
            float(row["turnover_total"]),
            get_metric(m44, ["turnover_total"]),
            get_metric(m67, ["turnover_total"]),
            get_metric(m63, ["turnover_total"]),
            get_metric(m37, ["turnover_total"]),
            None,
            None,
        ]
        table_tim = [
            float(row["time_in_market_frac"]),
            pm44["time_in_market_frac"],
            pm67["time_in_market_frac"],
            pm63["time_in_market_frac"],
            pm37["time_in_market_frac"],
            None,
            None,
        ]
        fig.add_trace(
            go.Table(
                header=dict(values=["Serie", "Equity Final", "CAGR", "MDD", "Sharpe", "Turnover", "Time In Market"], fill_color="#f0f0f0"),
                cells=dict(
                    values=[
                        table_rows,
                        [f"{v:,.2f}" if v is not None else "-" for v in table_equity],
                        [f"{v:.2%}" if v is not None else "-" for v in table_cagr],
                        [f"{v:.2%}" if v is not None else "-" for v in table_mdd],
                        [f"{v:.2f}" if v is not None else "-" for v in table_sharpe],
                        [f"{v:.2f}" if v is not None else "-" for v in table_turnover],
                        [f"{v:.2%}" if v is not None else "-" for v in table_tim],
                    ],
                    fill_color="white",
                ),
                name="Tabela de Metricas",
            ),
            row=3,
            col=1,
        )
        fig.update_layout(
            title="STATE 3 Phase 4B - Comparative (T068 Rally Protection vs T044/T067/T063/T037)",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
            height=1050,
        )
        fig.update_yaxes(title_text="Patrimonio (R$)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
        fig.update_xaxes(title_text="Data", row=2, col=1)
        fig.write_html(str(OUT_HTML), include_plotlyjs="cdn", full_html=True)

        metrics_snapshot = {
            "task_id": TASK_ID,
            "date_range_common": {
                "start": str(common_dates[0].date()),
                "end": str(common_dates[-1].date()),
                "n_dates": len(common_dates),
            },
            "cdi_source_used": cdi_source,
            "selection_winner": {
                "candidate_id": cfg["candidate_id"],
                "mode": cfg["mode"],
                "in_hyst_days": cfg["in_hyst_days"],
                "out_hyst_days": cfg["out_hyst_days"],
                "trend_window": cfg["trend_window"],
                "equity_final_total": float(row["equity_final_total"]),
                "excess_return_2023plus_vs_t044": float(row["excess_return_2023plus_vs_t044"]),
                "excess_return_rally_vs_t044": float(row["excess_return_rally_vs_t044"]),
            },
            "final_equity_norm": {
                "T068": float(wina["equity_norm"].iloc[-1]),
                "T044": float(t044a["equity_norm"].iloc[-1]),
                "T067": float(t067a["equity_norm"].iloc[-1]),
                "T063": float(t063a["equity_norm"].iloc[-1]),
                "T037": float(t037a["equity_norm"].iloc[-1]),
                "CDI": float(cdi_rebased[-1]),
                "IBOV": float(ibov_rebased.iloc[-1]),
            },
        }
        write_json_strict(OUT_METRICS_SNAPSHOT, metrics_snapshot)
        write_json_strict(
            OUT_PLOT_INVENTORY,
            {
                "task_id": TASK_ID,
                "output_html": str(OUT_HTML),
                "expected_equity_traces": 7,
                "expected_drawdown_traces": 5,
                "expected_table_traces": 1,
                "total_traces": len(fig.data),
                "trace_names": [trace.name for trace in fig.data],
            },
        )
        gates["G5_PLOTLY_PRESENT"] = "PASS" if OUT_HTML.exists() else "FAIL"
        gates["G6_TRACE_SIGNATURE"] = "PASS" if len(fig.data) == 13 else "FAIL"

        report_lines = [
            f"# {TASK_ID} Report",
            "",
            "## 1) Objetivo",
            "- Recuperar rali jun/2020-jul/2021 sem perder ganho 2023+ (vs T044), mantendo MDD controlado.",
            "",
            "## 2) Grid testado",
            f"- MODE_A={MODE_A}: IN={IN_HYST_GRID}, OUT={OUT_HYST_GRID}",
            f"- MODE_B={MODE_B}: IN={IN_HYST_GRID}, OUT={OUT_HYST_GRID}, TREND_WINDOW={TREND_WINDOW_GRID}",
            f"- fixed: slope_window={SLOPE_WINDOW}, cadence_days={CADENCE_DAYS}, buy_turnover_cap_ratio={BUY_TURNOVER_CAP_RATIO}",
            "",
            "## 3) Constraints e selecao",
            f"- hard_constraints: {THRESHOLDS}",
            f"- selection_order: {SELECTION_ORDER}",
            f"- selected_candidate_id: {cfg['candidate_id']}",
            "",
            "## 4) Winner metrics",
            f"- mode: {cfg['mode']}, in_hyst={cfg['in_hyst_days']}, out_hyst={cfg['out_hyst_days']}, trend_window={cfg['trend_window']}",
            f"- equity_final_total: {row['equity_final_total']:.2f}",
            f"- CAGR_total: {row['CAGR_total']:.6f}",
            f"- MDD_total: {row['MDD_total']:.6f}",
            f"- Sharpe_total: {row['Sharpe_total']:.6f}",
            f"- turnover_total: {row['turnover_total']:.6f}",
            f"- return_2023plus: {row['return_2023plus']:.6f}",
            f"- excess_return_2023plus_vs_t044: {row['excess_return_2023plus_vs_t044']:.6f}",
            f"- return_rally_2020_06_2021_07: {row['return_rally_2020_06_2021_07']:.6f}",
            f"- excess_return_rally_vs_t044: {row['excess_return_rally_vs_t044']:.6f}",
            "",
            "## 5) Artefatos",
            f"- `{OUT_ABLATION}`",
            f"- `{OUT_SELECTED_CFG}`",
            f"- `{OUT_CURVE}`",
            f"- `{OUT_LEDGER}`",
            f"- `{OUT_SUMMARY}`",
            f"- `{OUT_HTML}`",
            f"- `{OUT_METRICS_SNAPSHOT}`",
            f"- `{OUT_PLOT_INVENTORY}`",
            f"- `{OUT_REPORT}`",
            f"- `{OUT_MANIFEST}`",
        ]
        OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    ch_ok = update_changelog_one_line(TRACEABILITY_LINE)
    gates["G_CHLOG_UPDATED"] = "PASS" if ch_ok else "FAIL"

    script_path = Path(__file__).resolve()
    inputs_for_manifest = required_inputs + [script_path]
    outputs_for_manifest = [
        OUT_ABLATION,
        OUT_SELECTED_CFG,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_HTML,
        OUT_REPORT,
        OUT_CANDIDATE_SET,
        OUT_SELECTION_RULE,
        OUT_FEASIBILITY,
        OUT_METRICS_SNAPSHOT,
        OUT_PLOT_INVENTORY,
        OUT_MANIFEST,
        CHANGELOG_PATH,
    ]
    hash_targets = [p for p in inputs_for_manifest + outputs_for_manifest if p.exists() and p != OUT_MANIFEST]
    write_json_strict(
        OUT_MANIFEST,
        {
            "task_id": TASK_ID,
            "inputs_consumed": [str(p) for p in inputs_for_manifest],
            "outputs_produced": [str(p) for p in outputs_for_manifest],
            "hashes_sha256": {str(p): sha256_file(p) for p in hash_targets},
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
    if OUT_SELECTED_CFG.exists():
        print(f"- {OUT_SELECTED_CFG}")
    if OUT_CURVE.exists():
        print(f"- {OUT_CURVE}")
    if OUT_LEDGER.exists():
        print(f"- {OUT_LEDGER}")
    if OUT_SUMMARY.exists():
        print(f"- {OUT_SUMMARY}")
    if OUT_HTML.exists():
        print(f"- {OUT_HTML}")
    print(f"- {OUT_REPORT}")
    print(f"- {OUT_CANDIDATE_SET}")
    print(f"- {OUT_SELECTION_RULE}")
    print(f"- {OUT_FEASIBILITY}")
    if OUT_METRICS_SNAPSHOT.exists():
        print(f"- {OUT_METRICS_SNAPSHOT}")
    if OUT_PLOT_INVENTORY.exists():
        print(f"- {OUT_PLOT_INVENTORY}")
    print(f"- {OUT_MANIFEST}")
    print(f"- {CHANGELOG_PATH}")

    overall_pass = all(v == "PASS" for v in gates.values())
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
