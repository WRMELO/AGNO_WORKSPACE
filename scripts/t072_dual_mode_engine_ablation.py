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


TASK_ID = "T072-DUAL-MODE-ENGINE-ABLATION-V1"
BASE_CAPITAL = 100000.0
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

SCRIPT_BASE = ROOT / "scripts/t063_market_slope_reentry_ablation.py"
SPEC_FILE = ROOT / "02_Knowledge_Bank/docs/specs/SPEC-007_THERMOSTAT_FORNO_DUAL_MODE_T071.md"
LESSONS_FILE = ROOT / "02_Knowledge_Bank/docs/process/STATE3_PHASE4_LESSONS_LEARNED_T069.md"
GLOSSARY_FILE = ROOT / "02_Knowledge_Bank/docs/specs/GLOSSARY_OPERATIONAL.md"

INPUT_CANONICAL = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE.parquet"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
INPUT_BLACKLIST = ROOT / "src/data_engine/ssot/SSOT_QUALITY_BLACKLIST_A001.json"
INPUT_SCORES = ROOT / "src/data_engine/features/T037_M3_SCORES_DAILY.parquet"

INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T067_CURVE = ROOT / "src/data_engine/portfolio/T067_PORTFOLIO_CURVE_AGGRESSIVE.parquet"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_T067_SUMMARY = ROOT / "src/data_engine/portfolio/T067_BASELINE_SUMMARY_AGGRESSIVE.json"

OUT_SCRIPT = ROOT / "scripts/t072_dual_mode_engine_ablation.py"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
OUT_ABLATION = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_ABLATION_RESULTS.parquet"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_CURVE_DUAL_MODE.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_LEDGER_DUAL_MODE.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T072_BASELINE_SUMMARY_DUAL_MODE.json"
OUT_HTML = ROOT / "outputs/plots/T072_STATE3_PHASE5B_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T072-DUAL-MODE-ENGINE-ABLATION-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T072-DUAL-MODE-ENGINE-ABLATION-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T072-DUAL-MODE-ENGINE-ABLATION-V1_evidence"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_FEASIBILITY = OUT_EVIDENCE_DIR / "feasibility_snapshot.json"
OUT_METRICS_SNAPSHOT = OUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUT_PLOT_INVENTORY = OUT_EVIDENCE_DIR / "plot_inventory.json"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-01T16:00:00Z | EXEC: T072-DUAL-MODE-ENGINE-ABLATION-V1 <PASS/FAIL>. "
    "Artefatos: outputs/plots/T072_STATE3_PHASE5B_COMPARATIVE.html; "
    "outputs/governanca/T072-DUAL-MODE-ENGINE-ABLATION-V1_report.md; "
    "outputs/governanca/T072-DUAL-MODE-ENGINE-ABLATION-V1_manifest.json; "
    "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
)

MODE_A = "A_T037_PLENA_CARGA"
MODE_B = "B_T067_CONTROLE_REGIME"

PROFILE_A = {
    "cadence_days": 3,
    "top_n": 10,
    "target_pct": 0.10,
    "max_pct": 0.15,
}
PROFILE_B = {
    "cadence_days": 10,
    "top_n": 10,
    "target_pct": 0.10,
    "max_pct": 0.15,
    "market_slope_window": 30,
    "in_hyst_days": 4,
    "out_hyst_days": 4,
}

W_GRID = [30, 62, 90]
THR_GRID = [0.0000, 0.0005, 0.0010]
H_IN_GRID = [2, 3, 4]
H_OUT_GRID = [3, 4, 5]
SIGNAL_VARIANTS = ["SINAL-1", "SINAL-2"]
INITIAL_MODES = [MODE_A, MODE_B]

TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
P1_START = pd.Timestamp("2018-07-02")
P1_END = pd.Timestamp("2021-07-30")
P2_TRAIN_START = pd.Timestamp("2021-08-02")
P2_TRAIN_END = pd.Timestamp("2022-12-30")

THRESHOLDS = {
    "MDD_total_train_min": -0.30,
    "excess_return_P1_vs_T037_train_min": -0.20,
    "excess_return_P2train_vs_T067_min": -0.20,
    "MDD_holdout_min": -0.30,
    "excess_return_2023plus_vs_t044_holdout_min": 0.0,
}

SELECTION_ORDER = [
    "equity_final_total_train DESC",
    "min(excess_return_P1_vs_T037_train, excess_return_P2train_vs_T067) DESC",
    "Sharpe_train DESC",
    "turnover_total_train ASC",
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
    mode = c.get("mode", pd.Series("", index=c.index)).astype(str)
    return {
        "time_in_market_frac": float((exposure > 0).mean()) if len(exposure) else np.nan,
        "avg_exposure": float(exposure.mean()) if len(exposure.dropna()) else np.nan,
        "days_cash_ge_090_frac": float((cash_weight >= 0.90).mean()) if len(cash_weight) else np.nan,
        "days_mode_a_frac": float((mode == MODE_A).mean()) if len(mode) else np.nan,
        "days_mode_b_frac": float((mode == MODE_B).mean()) if len(mode) else np.nan,
    }


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


def subset_curve(curve: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None = None) -> pd.DataFrame:
    c = curve.copy()
    c["date"] = pd.to_datetime(c["date"], errors="coerce").dt.normalize()
    c = c[c["date"] >= start].copy()
    if end is not None:
        c = c[c["date"] <= end].copy()
    return c.sort_values("date").reset_index(drop=True)


def subset_ledger(ledger: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None = None) -> pd.DataFrame:
    if ledger.empty:
        return ledger.copy()
    l = ledger.copy()
    l["date"] = pd.to_datetime(l["date"], errors="coerce").dt.normalize()
    l = l[l["date"] >= start].copy()
    if end is not None:
        l = l[l["date"] <= end].copy()
    return l.sort_values("date").reset_index(drop=True)


def subperiod_return_rebased(curve: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None = None) -> float:
    c = subset_curve(curve, start, end)
    if len(c) < 2:
        return float("nan")
    eq = pd.to_numeric(c["equity_end"], errors="coerce").astype(float)
    if not np.isfinite(eq.iloc[0]) or eq.iloc[0] <= 0:
        return float("nan")
    return float(eq.iloc[-1] / eq.iloc[0] - 1.0)


def turnover_total_subset(ledger: pd.DataFrame, curve: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None = None) -> float:
    l = subset_ledger(ledger, start, end)
    c = subset_curve(curve, start, end)
    if c.empty:
        return float("nan")
    avg_equity = float(pd.to_numeric(c["equity_end"], errors="coerce").astype(float).mean())
    if avg_equity <= 0:
        return float("nan")
    if l.empty:
        return 0.0
    buy = float(l[l["side"] == "BUY"]["notional"].sum())
    sell = float(l[l["side"] == "SELL"]["notional"].sum())
    return float((buy + sell) / avg_equity)


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


def run_candidate_t072(
    base: Any,
    engine: Any,
    signal_w: int,
    thr: float,
    h_in: int,
    h_out: int,
    signal_variant: str,
    initial_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    px_wide = engine.px_wide
    z_wide = engine.z_wide
    macro_day = engine.macro_day
    scores_by_day = engine.scores_by_day
    sim_dates = engine.sim_dates
    market_mu_slope = base.compute_market_mu_slope(engine, slope_window=PROFILE_B["market_slope_window"])

    cash = float(base.INITIAL_CAPITAL)
    positions: dict[str, int] = {}
    ledger_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []

    # Mode controller state
    mode = initial_mode
    mode_switches = 0
    mode_day_idx = 0
    pos_streak = 0
    neg_streak = 0

    # Mode B defensive regime state (fixed T067 profile)
    regime_b_down = False
    b_down_streak = 0
    b_up_streak = 0
    b_regime_switches = 0

    # Severity pipeline state (Mode B)
    blocked_reentry: set[str] = set()
    pending_sell_exec: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    blocked_buy_events_regime = 0
    n_reentry_blocks = 0

    # Endogenous signal state histories (ANTI-LOOKAHEAD)
    burner_ret_hist: list[float] = []
    cdi_hist: list[float] = []
    net_prod_hist: list[float] = []
    cdi_credit_cum_hist: list[float] = []
    cdi_credit_cum = 0.0
    prev_positions_value_end = np.nan
    prev_net_val = np.nan

    for day_idx, d in enumerate(sim_dates):
        px_row = px_wide.loc[d]
        m = macro_day.loc[d]
        ibov = float(m["ibov_close"])

        # -----------------------------------------------------------
        # 1) Compute endogenous signal using ONLY past data (shift(1))
        # -----------------------------------------------------------
        if len(cdi_hist) >= signal_w:
            if signal_variant == "SINAL-1":
                signal_excess = float(np.sum(burner_ret_hist[-signal_w:]) - np.sum(cdi_hist[-signal_w:]))
            else:
                signal_excess = float(np.sum(net_prod_hist[-signal_w:]) - np.sum(cdi_hist[-signal_w:]))
        else:
            signal_excess = 0.0

        if signal_excess > thr:
            pos_streak += 1
            neg_streak = 0
        elif signal_excess < -thr:
            neg_streak += 1
            pos_streak = 0
        else:
            pos_streak = 0
            neg_streak = 0

        prev_mode = mode
        if mode != MODE_A and pos_streak >= h_in:
            mode = MODE_A
            pos_streak = 0
            neg_streak = 0
            mode_day_idx = 0
            mode_switches += 1
        elif mode != MODE_B and neg_streak >= h_out:
            mode = MODE_B
            pos_streak = 0
            neg_streak = 0
            mode_day_idx = 0
            mode_switches += 1

        # -----------------------------------------------------------
        # 2) Execute pending severity sells (D+1 queue, mode B only)
        # -----------------------------------------------------------
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
                    "mode": mode,
                }
            )
            blocked_reentry.add(ticker)

        # -----------------------------------------------------------
        # 3) Daily CDI on cash
        # -----------------------------------------------------------
        cdi_log = float(m["cdi_log_daily"]) if pd.notna(m["cdi_log_daily"]) else 0.0
        cdi_daily = float(np.exp(cdi_log) - 1.0)
        cash_before_cdi = cash
        cash *= 1.0 + cdi_daily
        cdi_credit = cash - cash_before_cdi
        cdi_credit_cum += cdi_credit

        # -----------------------------------------------------------
        # 4) Common trim above MAX_PCT (uses mode profile max/target)
        # -----------------------------------------------------------
        profile = PROFILE_A if mode == MODE_A else PROFILE_B
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
            if cur_pct <= profile["max_pct"]:
                continue
            target_val = profile["target_pct"] * equity_mid
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
                    "mode": mode,
                }
            )

        pos_val_mid = base.positions_value(positions, px_row)
        equity_mid = cash + pos_val_mid

        # -----------------------------------------------------------
        # 5) Mode-specific SELL logic
        # -----------------------------------------------------------
        regime_defensivo = False
        slope = float(market_mu_slope.loc[d]) if d in market_mu_slope.index else 0.0
        if mode == MODE_A:
            # Binary stress sell proxy: in_control_map False => stressed
            for ticker, qty in list(positions.items()):
                if qty <= 0:
                    continue
                stressed = not bool(engine.in_control_map.get((ticker, d), True))
                if not stressed:
                    continue
                px = float(px_row.get(ticker, np.nan))
                if not np.isfinite(px) or px <= 0:
                    continue
                notional = qty * px
                fee = notional * base.ORDER_COST_RATE
                cash_before = cash
                cash += notional - fee
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
                        "net_notional": notional - fee,
                        "cost_brl": fee,
                        "cash_before": cash_before,
                        "cash_after": cash,
                        "blocked_by_guardrail": False,
                        "mode": mode,
                    }
                )
        else:
            prev_regime = regime_b_down
            if not regime_b_down:
                enter_cond = slope < 0.0
                b_down_streak = b_down_streak + 1 if enter_cond else 0
                if b_down_streak >= PROFILE_B["out_hyst_days"]:
                    regime_b_down = True
                    b_down_streak = 0
                    b_up_streak = 0
            else:
                recover_cond = slope > 0.0
                b_up_streak = b_up_streak + 1 if recover_cond else 0
                if b_up_streak >= PROFILE_B["in_hyst_days"]:
                    regime_b_down = False
                    b_up_streak = 0
                    b_down_streak = 0
            regime_defensivo = bool(regime_b_down)
            if regime_defensivo != prev_regime:
                b_regime_switches += 1

            candidates: list[dict[str, Any]] = []
            if regime_defensivo:
                for ticker, qty in positions.items():
                    if qty <= 0 or ticker not in z_wide.columns:
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
                    if (z0 < 0.0) and (score >= 4):
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

        # -----------------------------------------------------------
        # 6) BUY logic (mode-specific cadence)
        # -----------------------------------------------------------
        profile = PROFILE_A if mode == MODE_A else PROFILE_B
        buy_day = mode_day_idx % int(profile["cadence_days"]) == 0
        if buy_day and d in scores_by_day and not regime_defensivo:
            day_scores = scores_by_day[d]
            top_candidates = day_scores[day_scores["m3_rank"] <= int(profile["top_n"])].sort_values("m3_rank")
            for row in top_candidates.itertuples():
                ticker = str(row.Index)
                if mode == MODE_B and ticker in blocked_reentry:
                    n_reentry_blocks += 1
                    continue
                px = float(px_row.get(ticker, np.nan))
                if not np.isfinite(px) or px <= 0:
                    continue
                cur_qty = int(positions.get(ticker, 0))
                cur_val = cur_qty * px
                target_val = float(profile["target_pct"]) * equity_mid
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
                cash_before = cash
                cash -= notional + fee
                positions[ticker] = cur_qty + qty_buy
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
                        "mode": mode,
                    }
                )
        elif buy_day and d in scores_by_day and regime_defensivo and mode == MODE_B:
            blocked_buy_events_regime += 1

        # -----------------------------------------------------------
        # 7) End-of-day accounting + append histories for next day
        # -----------------------------------------------------------
        pos_val_end = base.positions_value(positions, px_row)
        equity_end = cash + pos_val_end
        exposure = pos_val_end / equity_end if equity_end > 0 else 0.0
        benchmark = base.INITIAL_CAPITAL * (ibov / engine.ibov_base) if engine.ibov_base > 0 else np.nan
        n_positions = sum(1 for q in positions.values() if q > 0)

        # Auditor mitigation #1: safe signal with zero-division/NaN guard
        if np.isfinite(prev_positions_value_end) and prev_positions_value_end > 0 and np.isfinite(pos_val_end):
            burner_ret_1d = float(pos_val_end / prev_positions_value_end - 1.0)
        else:
            burner_ret_1d = 0.0
        burner_ret_hist.append(float(np.nan_to_num(burner_ret_1d, nan=0.0)))
        cdi_hist.append(float(np.nan_to_num(cdi_daily, nan=0.0)))

        net_val = float(equity_end - cdi_credit_cum)
        if np.isfinite(prev_net_val) and prev_net_val != 0 and np.isfinite(net_val):
            net_prod_1d = float(net_val / prev_net_val - 1.0)
        else:
            net_prod_1d = 0.0
        net_prod_hist.append(float(np.nan_to_num(net_prod_1d, nan=0.0)))
        cdi_credit_cum_hist.append(cdi_credit_cum)
        prev_positions_value_end = float(pos_val_end) if np.isfinite(pos_val_end) else np.nan
        prev_net_val = net_val if np.isfinite(net_val) else np.nan

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
                "mode": mode,
                "mode_switches_cumsum": int(mode_switches),
                "signal_excess_w": float(signal_excess),
                "signal_variant": signal_variant,
                "signal_w": int(signal_w),
                "signal_thr": float(thr),
                "signal_h_in": int(h_in),
                "signal_h_out": int(h_out),
                "regime_defensivo_b": bool(regime_defensivo),
                "market_mu_slope": float(slope),
                "b_regime_switches_cumsum": int(b_regime_switches),
                "blocked_buy_events_regime_cumsum": int(blocked_buy_events_regime),
                "n_reentry_blocks_cumsum": int(n_reentry_blocks),
            }
        )

        mode_day_idx += 1
        if mode != prev_mode:
            mode_day_idx = 1

    ledger = pd.DataFrame(ledger_rows)
    if not ledger.empty:
        ledger = ledger.sort_values(["date", "side", "ticker"]).reset_index(drop=True)
    curve = pd.DataFrame(curve_rows).sort_values("date").reset_index(drop=True)
    extra = {
        "mode_switches": int(curve["mode_switches_cumsum"].max()) if not curve.empty else 0,
        "b_regime_switches": int(curve["b_regime_switches_cumsum"].max()) if not curve.empty else 0,
        "n_reentry_blocks": int(curve["n_reentry_blocks_cumsum"].max()) if not curve.empty else 0,
        "blocked_buy_events_regime": int(curve["blocked_buy_events_regime_cumsum"].max()) if not curve.empty else 0,
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
        INPUT_T037_CURVE,
        INPUT_T044_CURVE,
        INPUT_T067_CURVE,
        INPUT_T037_SUMMARY,
        INPUT_T044_SUMMARY,
        INPUT_T067_SUMMARY,
        SCRIPT_BASE,
        SPEC_FILE,
        LESSONS_FILE,
        GLOSSARY_FILE,
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
    gates["G0_INPUTS_PRESENT"] = "PASS"

    OUT_ABLATION.parent.mkdir(parents=True, exist_ok=True)
    OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    base = _load_base_module()
    engine = base.prepare_engine_data()
    t037_curve_ref = pd.read_parquet(INPUT_T037_CURVE).copy()
    t044_curve_ref = pd.read_parquet(INPUT_T044_CURVE).copy()
    t067_curve_ref = pd.read_parquet(INPUT_T067_CURVE).copy()
    macro = pd.read_parquet(INPUT_MACRO).copy()
    t037_summary = parse_json_strict(INPUT_T037_SUMMARY)
    t044_summary = parse_json_strict(INPUT_T044_SUMMARY)
    t067_summary = parse_json_strict(INPUT_T067_SUMMARY)

    # Build candidate grid
    candidates: list[dict[str, Any]] = []
    for w in W_GRID:
        for thr in THR_GRID:
            for h_in in H_IN_GRID:
                for h_out in H_OUT_GRID:
                    for variant in SIGNAL_VARIANTS:
                        for initial_mode in INITIAL_MODES:
                            cid = f"W{w}_T{str(thr).replace('.', 'p')}_HI{h_in}_HO{h_out}_{variant}_{'A0' if initial_mode==MODE_A else 'B0'}"
                            candidates.append(
                                {
                                    "candidate_id": cid,
                                    "signal_w": int(w),
                                    "thr": float(thr),
                                    "h_in": int(h_in),
                                    "h_out": int(h_out),
                                    "signal_variant": variant,
                                    "initial_mode": initial_mode,
                                }
                            )
    write_json_strict(
        OUT_CANDIDATE_SET,
        {
            "task_id": TASK_ID,
            "grid": {
                "signal_w": W_GRID,
                "thr": THR_GRID,
                "h_in": H_IN_GRID,
                "h_out": H_OUT_GRID,
                "signal_variant": SIGNAL_VARIANTS,
                "initial_mode": INITIAL_MODES,
            },
            "candidate_count": len(candidates),
            "profiles_fixed": {"mode_a": PROFILE_A, "mode_b": PROFILE_B},
            "walk_forward": {
                "train_start": str(P1_START.date()),
                "train_end": str(TRAIN_END.date()),
                "holdout_start": str(HOLDOUT_START.date()),
            },
            "candidates": candidates,
        },
    )

    rows: list[dict[str, Any]] = []
    train_feasible: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None

    for cand in candidates:
        ledger, curve, extra = run_candidate_t072(
            base=base,
            engine=engine,
            signal_w=int(cand["signal_w"]),
            thr=float(cand["thr"]),
            h_in=int(cand["h_in"]),
            h_out=int(cand["h_out"]),
            signal_variant=str(cand["signal_variant"]),
            initial_mode=str(cand["initial_mode"]),
        )

        # Full metrics
        m_full = base.compute_metrics(curve["equity_end"])
        p_full = participation_metrics_safe(curve)
        t_full = base.turnover_total(ledger, curve)

        # Train metrics (for selection)
        curve_train = subset_curve(curve, P1_START, TRAIN_END)
        ledger_train = subset_ledger(ledger, P1_START, TRAIN_END)
        m_train = base.compute_metrics(curve_train["equity_end"]) if len(curve_train) >= 2 else {"cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
        t_train = turnover_total_subset(ledger_train, curve_train, P1_START, TRAIN_END)
        p1_ret_train = subperiod_return_rebased(curve_train, P1_START, P1_END)
        p1_t037_train = subperiod_return_rebased(t037_curve_ref, P1_START, P1_END)
        p2_ret_train = subperiod_return_rebased(curve_train, P2_TRAIN_START, P2_TRAIN_END)
        p2_t067_train = subperiod_return_rebased(t067_curve_ref, P2_TRAIN_START, P2_TRAIN_END)
        p1_excess_vs_t037_train = float(p1_ret_train - p1_t037_train) if np.isfinite(p1_ret_train) and np.isfinite(p1_t037_train) else np.nan
        p2_excess_vs_t067_train = float(p2_ret_train - p2_t067_train) if np.isfinite(p2_ret_train) and np.isfinite(p2_t067_train) else np.nan

        # Holdout gates
        curve_hold = subset_curve(curve, HOLDOUT_START, None)
        ledger_hold = subset_ledger(ledger, HOLDOUT_START, None)
        m_hold = base.compute_metrics(curve_hold["equity_end"]) if len(curve_hold) >= 2 else {"cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
        t_hold = turnover_total_subset(ledger_hold, curve_hold, HOLDOUT_START, None)
        ret_2023_hold = subperiod_return_rebased(curve_hold, HOLDOUT_START, None)
        ret_2023_t044 = subperiod_return_rebased(t044_curve_ref, HOLDOUT_START, None)
        excess_2023_vs_t044_hold = float(ret_2023_hold - ret_2023_t044) if np.isfinite(ret_2023_hold) and np.isfinite(ret_2023_t044) else np.nan

        # Full references
        eq_full = float(pd.to_numeric(curve["equity_end"], errors="coerce").astype(float).iloc[-1])
        eq_t044_full = float(pd.to_numeric(t044_curve_ref["equity_end"], errors="coerce").astype(float).iloc[-1])

        row = {
            "candidate_id": cand["candidate_id"],
            "signal_w": int(cand["signal_w"]),
            "thr": float(cand["thr"]),
            "h_in": int(cand["h_in"]),
            "h_out": int(cand["h_out"]),
            "signal_variant": cand["signal_variant"],
            "initial_mode": cand["initial_mode"],
            "equity_final_total_full": eq_full,
            "equity_final_t044_full_ref": eq_t044_full,
            "CAGR_full": float(m_full["cagr"]),
            "MDD_full": float(m_full["mdd"]),
            "Sharpe_full": float(m_full["sharpe"]),
            "turnover_total_full": float(t_full),
            "time_in_market_frac_full": float(p_full["time_in_market_frac"]),
            "avg_exposure_full": float(p_full["avg_exposure"]),
            "days_cash_ge_090_frac_full": float(p_full["days_cash_ge_090_frac"]),
            "days_mode_a_frac_full": float(p_full["days_mode_a_frac"]),
            "days_mode_b_frac_full": float(p_full["days_mode_b_frac"]),
            "equity_final_total_train": float(pd.to_numeric(curve_train["equity_end"], errors="coerce").astype(float).iloc[-1]) if len(curve_train) else np.nan,
            "CAGR_train": float(m_train["cagr"]),
            "MDD_train": float(m_train["mdd"]),
            "Sharpe_train": float(m_train["sharpe"]),
            "turnover_total_train": float(t_train),
            "return_P1_train": float(p1_ret_train),
            "return_P1_t037_train_ref": float(p1_t037_train),
            "excess_return_P1_vs_T037_train": float(p1_excess_vs_t037_train),
            "return_P2train": float(p2_ret_train),
            "return_P2train_t067_ref": float(p2_t067_train),
            "excess_return_P2train_vs_T067": float(p2_excess_vs_t067_train),
            "equity_final_total_holdout": float(pd.to_numeric(curve_hold["equity_end"], errors="coerce").astype(float).iloc[-1]) if len(curve_hold) else np.nan,
            "CAGR_holdout": float(m_hold["cagr"]),
            "MDD_holdout": float(m_hold["mdd"]),
            "Sharpe_holdout": float(m_hold["sharpe"]),
            "turnover_total_holdout": float(t_hold),
            "return_2023plus_holdout": float(ret_2023_hold),
            "return_2023plus_t044_holdout_ref": float(ret_2023_t044),
            "excess_return_2023plus_vs_t044_holdout": float(excess_2023_vs_t044_hold),
            "mode_switches_total": int(extra.get("mode_switches", 0)),
            "b_regime_switches_total": int(extra.get("b_regime_switches", 0)),
            "n_reentry_blocks_total": int(extra.get("n_reentry_blocks", 0)),
        }
        rows.append(row)

        feasible_train = (
            np.isfinite(row["MDD_train"])
            and row["MDD_train"] >= THRESHOLDS["MDD_total_train_min"]
            and np.isfinite(row["excess_return_P1_vs_T037_train"])
            and row["excess_return_P1_vs_T037_train"] >= THRESHOLDS["excess_return_P1_vs_T037_train_min"]
            and np.isfinite(row["excess_return_P2train_vs_T067"])
            and row["excess_return_P2train_vs_T067"] >= THRESHOLDS["excess_return_P2train_vs_T067_min"]
        )
        if feasible_train:
            train_feasible.append({"row": row, "cfg": cand, "curve": curve, "ledger": ledger})

    ablation_df = pd.DataFrame(rows).sort_values(
        ["equity_final_total_train", "Sharpe_train", "turnover_total_train"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    ablation_df.to_parquet(OUT_ABLATION, index=False)
    gates["G1_ABLATION_RESULTS_PRESENT"] = "PASS"

    # Deterministic selection on TRAIN only
    train_feasible_sorted = sorted(
        train_feasible,
        key=lambda x: (
            -x["row"]["equity_final_total_train"],
            -min(float(x["row"]["excess_return_P1_vs_T037_train"]), float(x["row"]["excess_return_P2train_vs_T067"])),
            -x["row"]["Sharpe_train"],
            x["row"]["turnover_total_train"],
            x["row"]["candidate_id"],
        ),
    )

    # Holdout gate recheck
    for item in train_feasible_sorted:
        row = item["row"]
        holdout_ok = (
            np.isfinite(row["MDD_holdout"])
            and row["MDD_holdout"] >= THRESHOLDS["MDD_holdout_min"]
            and np.isfinite(row["excess_return_2023plus_vs_t044_holdout"])
            and row["excess_return_2023plus_vs_t044_holdout"] >= THRESHOLDS["excess_return_2023plus_vs_t044_holdout_min"]
        )
        if holdout_ok:
            selected = item
            break

    write_json_strict(
        OUT_FEASIBILITY,
        {
            "task_id": TASK_ID,
            "thresholds": THRESHOLDS,
            "selection_order": SELECTION_ORDER,
            "candidate_count_total": int(len(candidates)),
            "candidate_count_train_feasible": int(len(train_feasible_sorted)),
            "candidate_ids_train_feasible": [i["row"]["candidate_id"] for i in train_feasible_sorted],
        },
    )

    if selected is None:
        gates["G2_WINNER_SELECTED"] = "FAIL"
        OUT_REPORT.write_text(
            "\n".join(
                [
                    f"# {TASK_ID} Report",
                    "",
                    "## Resultado",
                    "- Nenhum candidato passou simultaneamente nos hard constraints de TRAIN e gates de HOLDOUT.",
                    f"- candidatos_train_feasible: {len(train_feasible_sorted)}",
                    "",
                    "## Mitigacoes do Auditor T071",
                    "- Mitigacao NaN no sinal implementada (safe signal).",
                    "- Walk-forward implementado (TRAIN/HOLDOUT separados).",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        gates["G2_WINNER_SELECTED"] = "PASS"
        cfg = selected["cfg"]
        row = selected["row"]
        win_curve = selected["curve"].copy()
        win_ledger = selected["ledger"].copy()

        write_json_strict(
            OUT_SELECTED_CFG,
            {
                "task_id": TASK_ID,
                "selected_candidate_id": cfg["candidate_id"],
                "signal_w": cfg["signal_w"],
                "thr": cfg["thr"],
                "h_in": cfg["h_in"],
                "h_out": cfg["h_out"],
                "signal_variant": cfg["signal_variant"],
                "initial_mode": cfg["initial_mode"],
                "profiles_fixed": {"mode_a": PROFILE_A, "mode_b": PROFILE_B},
                "walk_forward": {
                    "train_start": str(P1_START.date()),
                    "train_end": str(TRAIN_END.date()),
                    "holdout_start": str(HOLDOUT_START.date()),
                    "holdout_end": str(pd.to_datetime(win_curve["date"]).max().date()),
                },
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
                "equity_final_full": row["equity_final_total_full"],
                "cagr_full": row["CAGR_full"],
                "mdd_full": row["MDD_full"],
                "sharpe_full": row["Sharpe_full"],
                "turnover_total_full": row["turnover_total_full"],
                "equity_final_train": row["equity_final_total_train"],
                "mdd_train": row["MDD_train"],
                "sharpe_train": row["Sharpe_train"],
                "excess_return_P1_vs_T037_train": row["excess_return_P1_vs_T037_train"],
                "excess_return_P2train_vs_T067": row["excess_return_P2train_vs_T067"],
                "equity_final_holdout": row["equity_final_total_holdout"],
                "mdd_holdout": row["MDD_holdout"],
                "sharpe_holdout": row["Sharpe_holdout"],
                "excess_return_2023plus_vs_t044_holdout": row["excess_return_2023plus_vs_t044_holdout"],
                "time_in_market_frac_full": row["time_in_market_frac_full"],
                "avg_exposure_full": row["avg_exposure_full"],
                "days_cash_ge_090_frac_full": row["days_cash_ge_090_frac_full"],
                "days_mode_a_frac_full": row["days_mode_a_frac_full"],
                "days_mode_b_frac_full": row["days_mode_b_frac_full"],
                "mode_switches_total": row["mode_switches_total"],
            },
        )
        write_json_strict(
            OUT_SELECTION_RULE,
            {
                "task_id": TASK_ID,
                "selection_scope": "TRAIN_ONLY",
                "holdout_gate_required": True,
                "constraints": THRESHOLDS,
                "selection_order": SELECTION_ORDER,
                "selected_candidate_id": cfg["candidate_id"],
            },
        )
        gates["G3_WINNER_ARTIFACTS_PRESENT"] = "PASS"

        # Plotly comparative
        for df in [win_curve, t037_curve_ref, t044_curve_ref, t067_curve_ref, macro]:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        common_dates = (
            set(win_curve["date"].dropna())
            & set(t037_curve_ref["date"].dropna())
            & set(t044_curve_ref["date"].dropna())
            & set(t067_curve_ref["date"].dropna())
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
        t037a = align_curve(t037_curve_ref)
        t044a = align_curve(t044_curve_ref)
        t067a = align_curve(t067_curve_ref)
        macroa = macro[macro["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)

        cdi_log = pd.to_numeric(macroa["cdi_log_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        cdi_growth = np.exp(np.cumsum(cdi_log.to_numpy(dtype=float)))
        cdi_rebased = BASE_CAPITAL * (cdi_growth / float(cdi_growth[0]))
        ibov_close = pd.to_numeric(macroa["ibov_close"], errors="coerce").ffill().bfill().astype(float)
        ibov_rebased = normalize_to_base(ibov_close)

        dd72 = compute_drawdown(wina["equity_norm"])
        dd37 = compute_drawdown(t037a["equity_norm"])
        dd44 = compute_drawdown(t044a["equity_norm"])
        dd67 = compute_drawdown(t067a["equity_norm"])

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.55, 0.25, 0.20],
            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
            subplot_titles=[
                "Equity Normalizada (Base R$100k): T072 vs T037 vs T044 vs T067 + CDI + IBOV",
                "Drawdown Overlay: T072 vs T037 vs T044 vs T067",
                "Tabela de Metricas (FULL)",
            ],
        )

        fig.add_trace(go.Scatter(x=wina["date"], y=wina["equity_norm"], mode="lines", name="T072 Dual-Mode", line=dict(color="#2ca02c", width=2.8)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t037a["date"], y=t037a["equity_norm"], mode="lines", name="T037 Baseline", line=dict(color="#1f77b4", dash="dot", width=1.9)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t044a["date"], y=t044a["equity_norm"], mode="lines", name="T044 Winner Phase2", line=dict(color="#d62728", dash="dash", width=2.0)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t067a["date"], y=t067a["equity_norm"], mode="lines", name="T067 Aggressive", line=dict(color="#ff7f0e", dash="dot", width=1.9)), row=1, col=1)
        fig.add_trace(go.Scatter(x=wina["date"], y=cdi_rebased, mode="lines", name="CDI Acumulado", line=dict(color="#7f7f7f", width=1.7)), row=1, col=1)
        fig.add_trace(go.Scatter(x=wina["date"], y=ibov_rebased, mode="lines", name="Ibovespa ^BVSP", line=dict(color="#111111", width=1.7)), row=1, col=1)

        fig.add_trace(go.Scatter(x=wina["date"], y=dd72, mode="lines", name="DD T072", line=dict(color="#2ca02c", width=1.9)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t037a["date"], y=dd37, mode="lines", name="DD T037", line=dict(color="#1f77b4", dash="dot", width=1.6)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t044a["date"], y=dd44, mode="lines", name="DD T044", line=dict(color="#d62728", dash="dash", width=1.6)), row=2, col=1)
        fig.add_trace(go.Scatter(x=t067a["date"], y=dd67, mode="lines", name="DD T067", line=dict(color="#ff7f0e", dash="dot", width=1.6)), row=2, col=1)

        mode_mask = (wina["mode"] == MODE_B).astype(bool)
        for x0, x1 in find_true_intervals(mode_mask, wina["date"]):
            fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(255, 127, 14, 0.08)", line_width=0, layer="below", row=1, col=1)
            fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(255, 127, 14, 0.08)", line_width=0, layer="below", row=2, col=1)

        pm72 = participation_metrics_safe(wina)
        pm37 = participation_metrics_safe(t037a)
        pm44 = participation_metrics_safe(t044a)
        pm67 = participation_metrics_safe(t067a)
        bm_cdi = benchmark_metrics(pd.Series(cdi_rebased))
        bm_ibov = benchmark_metrics(pd.Series(ibov_rebased))

        table_rows = ["T072", "T037", "T044", "T067", "CDI", "IBOV"]
        table_equity = [
            float(wina["equity_norm"].iloc[-1]),
            float(t037a["equity_norm"].iloc[-1]),
            float(t044a["equity_norm"].iloc[-1]),
            float(t067a["equity_norm"].iloc[-1]),
            float(cdi_rebased[-1]),
            float(ibov_rebased.iloc[-1]),
        ]
        table_cagr = [
            float(row["CAGR_full"]),
            get_metric(t037_summary, ["cagr", "CAGR"]),
            get_metric(t044_summary.get("metrics_total", {}), ["CAGR", "cagr"]),
            get_metric(t067_summary, ["cagr", "CAGR"]),
            bm_cdi["cagr"],
            bm_ibov["cagr"],
        ]
        table_mdd = [
            float(row["MDD_full"]),
            get_metric(t037_summary, ["mdd", "MDD"]),
            get_metric(t044_summary.get("metrics_total", {}), ["MDD", "mdd"]),
            get_metric(t067_summary, ["mdd", "MDD"]),
            bm_cdi["mdd"],
            bm_ibov["mdd"],
        ]
        table_sharpe = [
            float(row["Sharpe_full"]),
            get_metric(t037_summary, ["sharpe"]),
            get_metric(t044_summary.get("metrics_total", {}), ["sharpe"]),
            get_metric(t067_summary, ["sharpe"]),
            bm_cdi["sharpe"],
            bm_ibov["sharpe"],
        ]
        table_turnover = [
            float(row["turnover_total_full"]),
            get_metric(t037_summary, ["turnover_total"]),
            get_metric(t044_summary.get("metrics_total", {}), ["turnover_total"]),
            get_metric(t067_summary, ["turnover_total"]),
            None,
            None,
        ]
        table_tim = [
            float(pm72["time_in_market_frac"]),
            float(pm37["time_in_market_frac"]),
            float(pm44["time_in_market_frac"]),
            float(pm67["time_in_market_frac"]),
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
            title="STATE 3 Phase 5B - Comparative (T072 Dual-Mode vs T037/T044/T067)",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
            height=1040,
        )
        fig.update_yaxes(title_text="Patrimonio (R$)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
        fig.update_xaxes(title_text="Data", row=2, col=1)
        fig.write_html(str(OUT_HTML), include_plotlyjs="cdn", full_html=True)
        gates["G4_PLOTLY_PRESENT"] = "PASS" if OUT_HTML.exists() else "FAIL"

        metrics_snapshot = {
            "task_id": TASK_ID,
            "date_range_common": {
                "start": str(common_dates[0].date()),
                "end": str(common_dates[-1].date()),
                "n_dates": len(common_dates),
            },
            "selected_candidate": cfg["candidate_id"],
            "selected_params": cfg,
            "train_metrics": {
                "equity_final_total_train": row["equity_final_total_train"],
                "MDD_train": row["MDD_train"],
                "Sharpe_train": row["Sharpe_train"],
                "excess_return_P1_vs_T037_train": row["excess_return_P1_vs_T037_train"],
                "excess_return_P2train_vs_T067": row["excess_return_P2train_vs_T067"],
            },
            "holdout_metrics": {
                "equity_final_total_holdout": row["equity_final_total_holdout"],
                "MDD_holdout": row["MDD_holdout"],
                "Sharpe_holdout": row["Sharpe_holdout"],
                "excess_return_2023plus_vs_t044_holdout": row["excess_return_2023plus_vs_t044_holdout"],
            },
            "full_metrics": {
                "equity_final_total_full": row["equity_final_total_full"],
                "MDD_full": row["MDD_full"],
                "Sharpe_full": row["Sharpe_full"],
                "turnover_total_full": row["turnover_total_full"],
                "days_mode_a_frac_full": row["days_mode_a_frac_full"],
                "days_mode_b_frac_full": row["days_mode_b_frac_full"],
                "mode_switches_total": row["mode_switches_total"],
            },
            "auditor_t071_mitigations": {
                "nan_signal_safe": "Implemented: when positions_value_end<=0, burner_ret_1d=0.0 and fillna(0) in rolling signal.",
                "walk_forward_split": "Implemented: TRAIN=2018-07-02..2022-12-30, HOLDOUT=2023-01-02..end; selection on TRAIN only.",
            },
        }
        write_json_strict(OUT_METRICS_SNAPSHOT, metrics_snapshot)
        write_json_strict(
            OUT_PLOT_INVENTORY,
            {
                "task_id": TASK_ID,
                "output_html": str(OUT_HTML),
                "expected_equity_traces": 6,
                "expected_drawdown_traces": 4,
                "expected_table_traces": 1,
                "total_traces": len(fig.data),
                "trace_names": [trace.name for trace in fig.data],
            },
        )

        report_lines = [
            f"# {TASK_ID} Report",
            "",
            "## 1) Objetivo",
            "- Implementar motor dual-mode (T037/T067) com termostato endogeno e ablar parametros de comutacao sem usar data fixa.",
            "",
            "## 2) Walk-forward (mitigacao Auditor T071)",
            f"- TRAIN: {P1_START.date()} .. {TRAIN_END.date()}",
            f"- HOLDOUT: {HOLDOUT_START.date()} .. {pd.to_datetime(win_curve['date']).max().date()}",
            "- Selecao feita somente no TRAIN; HOLDOUT usado como gate de validacao.",
            "",
            "## 3) Grid testado",
            f"- W_GRID={W_GRID}",
            f"- THR_GRID={THR_GRID}",
            f"- H_IN_GRID={H_IN_GRID}",
            f"- H_OUT_GRID={H_OUT_GRID}",
            f"- SIGNAL_VARIANTS={SIGNAL_VARIANTS}",
            f"- INITIAL_MODES={INITIAL_MODES}",
            f"- candidate_count={len(candidates)}",
            "",
            "## 4) Constraints e selecao",
            f"- thresholds={THRESHOLDS}",
            f"- selection_order={SELECTION_ORDER}",
            f"- selected_candidate_id={cfg['candidate_id']}",
            "",
            "## 5) Winner metrics",
            f"- TRAIN: equity={row['equity_final_total_train']:.2f}, MDD={row['MDD_train']:.6f}, Sharpe={row['Sharpe_train']:.6f}, excess_P1_vs_T037={row['excess_return_P1_vs_T037_train']:.6f}, excess_P2train_vs_T067={row['excess_return_P2train_vs_T067']:.6f}",
            f"- HOLDOUT: equity={row['equity_final_total_holdout']:.2f}, MDD={row['MDD_holdout']:.6f}, Sharpe={row['Sharpe_holdout']:.6f}, excess_2023plus_vs_T044={row['excess_return_2023plus_vs_t044_holdout']:.6f}",
            f"- FULL: equity={row['equity_final_total_full']:.2f}, MDD={row['MDD_full']:.6f}, Sharpe={row['Sharpe_full']:.6f}, turnover={row['turnover_total_full']:.6f}",
            "",
            "## 6) Mitigacoes explicitas dos riscos do Auditor T071",
            "- Risco NaN no sinal: mitigado com regra safe (`positions_value_end<=0 => burner_ret_1d=0`) e `fillna(0)`.",
            "- Risco de walk-forward indefinido: mitigado com split fixo TRAIN/HOLDOUT e selecao no TRAIN apenas.",
            "",
            "## 7) Artefatos",
            f"- `{OUT_SCRIPT}`",
            f"- `{OUT_SELECTED_CFG}`",
            f"- `{OUT_ABLATION}`",
            f"- `{OUT_CURVE}`",
            f"- `{OUT_LEDGER}`",
            f"- `{OUT_SUMMARY}`",
            f"- `{OUT_HTML}`",
            f"- `{OUT_REPORT}`",
            f"- `{OUT_MANIFEST}`",
        ]
        OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    ch_ok = update_changelog_one_line(TRACEABILITY_LINE)
    gates["G_CHLOG_UPDATED"] = "PASS" if ch_ok else "FAIL"

    script_path = Path(__file__).resolve()
    inputs_for_manifest = required_inputs + [script_path]
    outputs_for_manifest = [
        OUT_SCRIPT,
        OUT_SELECTED_CFG,
        OUT_ABLATION,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_HTML,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_CANDIDATE_SET,
        OUT_SELECTION_RULE,
        OUT_FEASIBILITY,
        OUT_METRICS_SNAPSHOT,
        OUT_PLOT_INVENTORY,
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
    for p in [
        OUT_SCRIPT,
        OUT_SELECTED_CFG,
        OUT_ABLATION,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_HTML,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_CANDIDATE_SET,
        OUT_SELECTION_RULE,
        OUT_FEASIBILITY,
        OUT_METRICS_SNAPSHOT,
        OUT_PLOT_INVENTORY,
        CHANGELOG_PATH,
    ]:
        if p.exists():
            print(f"- {p}")

    overall_pass = all(v == "PASS" for v in gates.values())
    print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
