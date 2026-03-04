#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T126"
RUN_ID = "T126-US-ENGINE-V2-TRIGGER-BACKTEST-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_SCORES = ROOT / "src/data_engine/features/T120_M3_US_SCORES_DAILY.parquet"
IN_SSOT_US = ROOT / "src/data_engine/ssot/SSOT_CANONICAL_BASE_US.parquet"
IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"
IN_UNIVERSE = ROOT / "src/data_engine/ssot/SSOT_US_UNIVERSE_OPERATIONAL_PHASE10.parquet"
IN_T122_CFG = ROOT / "src/data_engine/portfolio/T122_SELECTED_CONFIG_US_ENGINE_NPOS_CADENCE.json"
IN_T122_CURVE = ROOT / "src/data_engine/portfolio/T122_US_ENGINE_WINNER_CURVE_DAILY.parquet"
IN_T125_SIGNALS = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_SIGNALS_DAILY.parquet"
IN_T125_CFG = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_SELECTED_CONFIG.json"
IN_T125_TIMING = ROOT / "src/data_engine/features/T125_US_V2_TRIGGER_TIMING_SP500_CURVE_DAILY.parquet"
IN_T115_CURVE = ROOT / "src/data_engine/portfolio/T115_US_FACTORY_CURVE_DAILY.parquet"

OUT_SCRIPT = ROOT / "scripts/t126_backtest_us_engine_with_trigger_v2_v1.py"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T126_US_ENGINE_V2_TRIGGER_CURVE_DAILY.parquet"
OUT_LEDGER = ROOT / "src/data_engine/portfolio/T126_US_ENGINE_V2_TRIGGER_LEDGER.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T126_US_ENGINE_V2_TRIGGER_SUMMARY.json"
OUT_PLOT = ROOT / "outputs/plots/T126_STATE3_PHASE10D_US_ENGINE_V2_TRIGGER_BACKTEST.html"
OUT_REPORT = ROOT / "outputs/governanca/T126-US-ENGINE-V2-TRIGGER-BACKTEST-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T126-US-ENGINE-V2-TRIGGER-BACKTEST-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T126-US-ENGINE-V2-TRIGGER-BACKTEST-V1_evidence"
OUT_PREFLIGHT = OUT_EVID / "input_preflight.json"
OUT_JOIN = OUT_EVID / "join_coverage.json"
OUT_BASELINE_REG = OUT_EVID / "baseline_regression_t122.json"
OUT_TRIGGER_REG = OUT_EVID / "trigger_timing_regression_t125.json"
OUT_METRICS = OUT_EVID / "metrics_snapshot.json"
OUT_MDD_CHECK = OUT_EVID / "mdd_hard_constraint_check.json"

INITIAL_CAPITAL = 100000.0
TRAIN_START = pd.Timestamp("2018-07-02")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
HOLDOUT_END = pd.Timestamp("2026-02-26")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")
EXPECTED_ROWS = 1852

TRACEABILITY_LINE = "- 2026-03-04T23:45:00Z | EXEC: T126 PASS. Backtest integrado Motor US (TopN=5,Cad=10,T122) + ML Trigger US v2 (T125/C090 thr=0.45,h_in=3,h_out=5) com cash tank Fed funds e custos 1bp; comparativos vs SP500 BH/cash/T122/T115 (ref) + evidências de regressão (T122 e timing T125) e checagem de hard constraint MDD HOLDOUT>=-0.15 (informativo). Artefatos: scripts/t126_backtest_us_engine_with_trigger_v2_v1.py; src/data_engine/portfolio/T126_US_ENGINE_V2_TRIGGER_{CURVE_DAILY,LEDGER,SUMMARY}.parquet; outputs/plots/T126_STATE3_PHASE10D_US_ENGINE_V2_TRIGGER_BACKTEST.html; outputs/governanca/T126-US-ENGINE-V2-TRIGGER-BACKTEST-V1_{report,manifest}.json"


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    if pd.isna(obj):
        return None
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_changelog_one_line_idempotent(line: str) -> bool:
    if not CHANGELOG_PATH.exists():
        return False
    existing = CHANGELOG_PATH.read_text(encoding="utf-8")
    if line in existing:
        return True
    text = existing
    if text and not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return line in CHANGELOG_PATH.read_text(encoding="utf-8")


def compute_mdd(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").ffill().fillna(INITIAL_CAPITAL).to_numpy(dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = eq / np.maximum(peak, 1e-12) - 1.0
    return float(np.min(dd))


def compute_sharpe(ret_1d: pd.Series) -> float:
    r = pd.to_numeric(ret_1d, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(r) < 2:
        return 0.0
    sd = float(np.std(r, ddof=1))
    if sd <= 0:
        return 0.0
    return float(np.mean(r) / sd * np.sqrt(252.0))


def compute_cagr(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").ffill().fillna(INITIAL_CAPITAL).to_numpy(dtype=float)
    if len(eq) < 2 or eq[0] <= 0:
        return 0.0
    years = len(eq) / 252.0
    if years <= 0:
        return 0.0
    return float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0)


def split_label(d: pd.Timestamp) -> str:
    return "TRAIN" if d <= TRAIN_END else "HOLDOUT"


def count_switches(s: pd.Series) -> int:
    x = pd.to_numeric(s, errors="coerce").fillna(0).astype(int).to_numpy()
    if len(x) <= 1:
        return 0
    return int(np.sum(x[1:] != x[:-1]))


def equity_metrics(df: pd.DataFrame, equity_col: str) -> dict[str, float]:
    if len(df) == 0:
        return {"rows": 0.0, "equity_end": INITIAL_CAPITAL, "cagr": 0.0, "mdd": 0.0, "sharpe": 0.0}
    eq = pd.to_numeric(df[equity_col], errors="coerce").ffill().fillna(INITIAL_CAPITAL)
    ret = eq.pct_change().fillna(0.0)
    return {
        "rows": float(len(df)),
        "equity_end": float(eq.iloc[-1]),
        "cagr": compute_cagr(eq),
        "mdd": compute_mdd(eq),
        "sharpe": compute_sharpe(ret),
    }


def make_report(gates: list[Gate], retry_log: list[str], artifacts: list[Path], status_txt: str) -> str:
    lines: list[str] = [
        f"# HEADER: {TASK_ID}",
        "",
        "## STEP GATES",
    ]
    for g in gates:
        lines.append(f"- {'PASS' if g.passed else 'FAIL'} | {g.name} | {g.detail}")
    lines.extend(["", "## RETRY LOG"])
    if retry_log:
        lines.extend([f"- {r}" for r in retry_log])
    else:
        lines.append("- none")
    lines.extend(["", "## ARTIFACT LINKS"])
    for p in artifacts:
        if p.exists():
            lines.append(f"- {p.relative_to(ROOT)}")
    lines.append("")
    lines.append(f"OVERALL STATUS: [[ {status_txt} ]]")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    overall_pass = True

    artifacts = [
        OUT_SCRIPT,
        OUT_CURVE,
        OUT_LEDGER,
        OUT_SUMMARY,
        OUT_PLOT,
        OUT_REPORT,
        OUT_MANIFEST,
        OUT_PREFLIGHT,
        OUT_JOIN,
        OUT_BASELINE_REG,
        OUT_TRIGGER_REG,
        OUT_METRICS,
        OUT_MDD_CHECK,
    ]

    for p in [OUT_CURVE, OUT_LEDGER, OUT_SUMMARY, OUT_PLOT, OUT_REPORT, OUT_MANIFEST]:
        p.parent.mkdir(parents=True, exist_ok=True)
    OUT_EVID.mkdir(parents=True, exist_ok=True)

    try:
        in_venv = (".venv" in sys.executable) and (Path(sys.executable).resolve() == PYTHON_ENV.resolve())
        gates.append(Gate("G_ENV_VENV", in_venv, f"python={sys.executable}"))
        if not in_venv:
            raise RuntimeError("FATAL: execute with .venv python")

        dep_ok = True
        try:
            proc = subprocess.run([str(ROOT / ".venv/bin/pip"), "list"], check=True, capture_output=True, text=True)
            txt = proc.stdout.lower()
            for dep in ("pandas", "numpy", "plotly"):
                if dep not in txt:
                    dep_ok = False
        except Exception as e:
            dep_ok = False
            retry_log.append(f"pip list error: {type(e).__name__}: {e}")
        gates.append(Gate("G_DEPENDENCIES_CHECK", dep_ok, "pip list baseline"))

        inputs_present = all(
            p.exists()
            for p in [
                IN_SCORES,
                IN_SSOT_US,
                IN_MACRO,
                IN_UNIVERSE,
                IN_T122_CFG,
                IN_T122_CURVE,
                IN_T125_SIGNALS,
                IN_T125_CFG,
                IN_T125_TIMING,
                CHANGELOG_PATH,
            ]
        )
        gates.append(Gate("G_INPUTS_PRESENT", inputs_present, "required inputs + changelog"))
        if not inputs_present:
            raise RuntimeError("T126 required inputs missing")

        cfg_t122 = json.loads(IN_T122_CFG.read_text(encoding="utf-8"))
        top_n = int(cfg_t122.get("winner_top_n", 5))
        cadence_days = int(cfg_t122.get("winner_cadence_days", 10))
        cost_rate = float(cfg_t122.get("config_fixed", {}).get("cost_rate_one_way", 0.0001))

        cfg_t125 = json.loads(IN_T125_CFG.read_text(encoding="utf-8"))
        thr = float(cfg_t125.get("threshold", 0.45))
        h_in = int(cfg_t125.get("h_in", 3))
        h_out = int(cfg_t125.get("h_out", 5))
        trig_winner = str(cfg_t125.get("winner_candidate_id", "UNKNOWN"))

        universe = pd.read_parquet(IN_UNIVERSE, columns=["ticker"]).copy()
        universe["ticker"] = universe["ticker"].astype(str).str.upper().str.strip()
        use_tickers = set(universe["ticker"].tolist())
        gates.append(Gate("G_UNIVERSE_496", len(use_tickers) == 496, f"n_tickers={len(use_tickers)}"))

        scores = pd.read_parquet(IN_SCORES).copy()
        scores["date"] = pd.to_datetime(scores["date"], errors="coerce").dt.normalize()
        scores["ticker"] = scores["ticker"].astype(str).str.upper().str.strip()
        scores = scores[scores["ticker"].isin(use_tickers)].copy()
        req_cols = {"date", "ticker", "m3_rank_us_exec", "score_m3_us_exec"}
        schema_ok = req_cols.issubset(set(scores.columns))
        gates.append(Gate("G_SCORE_SCHEMA_OK", schema_ok, f"required_exec_cols={schema_ok}"))
        if not schema_ok:
            raise RuntimeError("missing *_exec columns in T120")

        scores = scores.dropna(subset=["m3_rank_us_exec", "score_m3_us_exec"]).copy()
        scores["m3_rank_us_exec"] = pd.to_numeric(scores["m3_rank_us_exec"], errors="coerce")
        scores = scores.dropna(subset=["m3_rank_us_exec"]).copy()
        scores["m3_rank_us_exec"] = scores["m3_rank_us_exec"].astype(int)
        by_day: dict[pd.Timestamp, pd.DataFrame] = {}
        for d, g in scores.groupby("date", sort=True):
            by_day[pd.Timestamp(d)] = g.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True]).copy()

        ssot = pd.read_parquet(IN_SSOT_US, columns=["date", "ticker", "close_operational"]).copy()
        ssot["date"] = pd.to_datetime(ssot["date"], errors="coerce").dt.normalize()
        ssot["ticker"] = ssot["ticker"].astype(str).str.upper().str.strip()
        ssot["close_operational"] = pd.to_numeric(ssot["close_operational"], errors="coerce")
        ssot = ssot.dropna(subset=["date", "ticker", "close_operational"]).copy()
        ssot = ssot[(ssot["close_operational"] > 0) & (ssot["ticker"].isin(use_tickers))].copy()
        px_wide = ssot.pivot_table(index="date", columns="ticker", values="close_operational", aggfunc="first").sort_index().ffill()

        macro = pd.read_parquet(IN_MACRO, columns=["date", "sp500_close", "fed_funds_rate"]).copy()
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
        macro["sp500_close"] = pd.to_numeric(macro["sp500_close"], errors="coerce")
        macro["fed_funds_rate"] = pd.to_numeric(macro["fed_funds_rate"], errors="coerce")
        macro = macro.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")
        macro["sp500_close"] = macro["sp500_close"].ffill().bfill()
        macro["fed_funds_rate"] = macro["fed_funds_rate"].ffill().bfill()
        macro["cash_log_daily_us"] = np.log1p((macro["fed_funds_rate"] / 100.0) / 252.0)
        macro_day = macro.set_index("date")

        score_dates = set(by_day.keys())
        sim_dates = sorted(set(px_wide.index).intersection(set(macro_day.index)).intersection(score_dates))
        sim_dates = [d for d in sim_dates if TRAIN_START <= d <= HOLDOUT_END]
        common_ok = bool(len(sim_dates) == EXPECTED_ROWS and sim_dates[0] == TRAIN_START and sim_dates[-1] == HOLDOUT_END)
        gates.append(
            Gate(
                "G_COMMON_DATES_OK",
                common_ok,
                f"rows={len(sim_dates)} min={sim_dates[0] if sim_dates else None} max={sim_dates[-1] if sim_dates else None}",
            )
        )
        if not sim_dates:
            raise RuntimeError("no simulation dates")

        signals = pd.read_parquet(IN_T125_SIGNALS).copy()
        signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()
        sig_sim = pd.DataFrame({"date": sim_dates}).merge(
            signals[["date", "state_cash", "selected_candidate_id", "threshold", "h_in", "h_out"]],
            on="date",
            how="left",
        )
        join_ok = len(sig_sim) == len(sim_dates) and int(sig_sim["state_cash"].isna().sum()) == 0
        gates.append(
            Gate(
                "G_TRIGGER_JOIN_COVERAGE",
                join_ok,
                f"rows={len(sig_sim)}/{len(sim_dates)} nan_state={int(sig_sim['state_cash'].isna().sum())}",
            )
        )
        if not join_ok:
            raise RuntimeError("trigger join coverage failed")
        sig_sim["state_cash"] = pd.to_numeric(sig_sim["state_cash"], errors="coerce").fillna(0).astype(int)
        sig_sim["selected_candidate_id"] = sig_sim["selected_candidate_id"].astype(str)
        sig_by_date = sig_sim.set_index("date")

        prices_start = float(macro_day.loc[TRAIN_START, "sp500_close"])
        cash = INITIAL_CAPITAL
        cash_bench = INITIAL_CAPITAL
        sp500_bench = INITIAL_CAPITAL
        positions: dict[str, float] = {}
        days_since_rebal = 10**9
        prev_state_cash = 0
        total_cost_paid = 0.0
        rows: list[dict[str, Any]] = []
        ledger: list[dict[str, Any]] = []

        for i, d in enumerate(sim_dates):
            cash_log = float(macro_day.loc[d, "cash_log_daily_us"])
            cash *= float(np.exp(cash_log))
            cash_bench *= float(np.exp(cash_log))
            px_row = px_wide.loc[d]

            state_cash = int(sig_by_date.loc[d, "state_cash"])
            current_values: dict[str, float] = {}
            for t, q in positions.items():
                px = float(px_row.get(t, np.nan))
                if np.isfinite(px) and px > 0 and q > 0:
                    current_values[t] = q * px
            port_before = float(sum(current_values.values()))
            equity_before = cash + port_before

            turnover_notional = 0.0
            cost_paid = 0.0
            n_selected = 0
            rebalance_reason = "hold"

            if state_cash == 1:
                if port_before > 0:
                    sells = float(port_before)
                    turnover_notional = sells
                    cost_paid = float(turnover_notional * cost_rate)
                    total_cost_paid += cost_paid
                    cash = cash + sells - cost_paid
                    positions = {}
                    rebalance_reason = "trigger_cash_liquidation"
                    ledger.append(
                        {
                            "date": d,
                            "reason": rebalance_reason,
                            "state_cash": state_cash,
                            "turnover_notional": turnover_notional,
                            "cost_paid": cost_paid,
                            "n_selected": 0,
                            "equity_before": equity_before,
                        }
                    )
                days_since_rebal += 1
            else:
                do_rebal = (i == 0) or (days_since_rebal >= cadence_days) or (prev_state_cash == 1)
                if do_rebal:
                    day_scores = by_day.get(d, pd.DataFrame()).copy()
                    selected: list[str] = []
                    if len(day_scores) > 0:
                        selected = day_scores.sort_values(["m3_rank_us_exec", "ticker"], ascending=[True, True]).head(top_n)[
                            "ticker"
                        ].tolist()
                    n_selected = len(selected)

                    target_values: dict[str, float] = {}
                    if n_selected > 0:
                        w = 1.0 / n_selected
                        for t in selected:
                            px = float(px_row.get(t, np.nan))
                            if np.isfinite(px) and px > 0:
                                target_values[t] = equity_before * w

                    all_tickers = set(current_values.keys()).union(set(target_values.keys()))
                    sells = 0.0
                    buys = 0.0
                    new_positions: dict[str, float] = {}
                    for t in sorted(all_tickers):
                        cur_v = float(current_values.get(t, 0.0))
                        tgt_v = float(target_values.get(t, 0.0))
                        delta = tgt_v - cur_v
                        if delta < 0:
                            sells += -delta
                        elif delta > 0:
                            buys += delta
                        if tgt_v > 0:
                            px = float(px_row.get(t, np.nan))
                            if np.isfinite(px) and px > 0:
                                new_positions[t] = tgt_v / px

                    turnover_notional = float(sells + buys)
                    cost_paid = float(turnover_notional * cost_rate)
                    total_cost_paid += cost_paid
                    cash = cash + sells - buys - cost_paid
                    positions = new_positions
                    days_since_rebal = 0
                    rebalance_reason = "reentry_from_cash" if prev_state_cash == 1 else ("initial" if i == 0 else "cadence")
                    ledger.append(
                        {
                            "date": d,
                            "reason": rebalance_reason,
                            "state_cash": state_cash,
                            "turnover_notional": turnover_notional,
                            "cost_paid": cost_paid,
                            "n_selected": n_selected,
                            "equity_before": equity_before,
                        }
                    )
                else:
                    days_since_rebal += 1
                    n_selected = len(positions)

            curr_values = 0.0
            for t, q in positions.items():
                px = float(px_row.get(t, np.nan))
                if np.isfinite(px) and px > 0 and q > 0:
                    curr_values += q * px
            equity = float(cash + curr_values)
            spx = float(macro_day.loc[d, "sp500_close"])
            sp500_bench = float(INITIAL_CAPITAL * (spx / prices_start))

            rows.append(
                {
                    "date": d,
                    "split": split_label(d),
                    "state_cash": state_cash,
                    "selected_candidate_id": str(sig_by_date.loc[d, "selected_candidate_id"]),
                    "threshold": float(sig_by_date.loc[d, "threshold"]),
                    "h_in": int(sig_by_date.loc[d, "h_in"]),
                    "h_out": int(sig_by_date.loc[d, "h_out"]),
                    "equity_strategy": equity,
                    "equity_sp500_bh": sp500_bench,
                    "equity_cash_fedfunds": cash_bench,
                    "n_selected": int(n_selected),
                    "turnover_notional": float(turnover_notional),
                    "cost_paid": float(cost_paid),
                    "top_n": int(top_n),
                    "cadence_days": int(cadence_days),
                    "rebalance_reason": rebalance_reason,
                }
            )
            prev_state_cash = state_cash

        curve = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        curve["ret_strategy_1d"] = curve["equity_strategy"].pct_change().fillna(0.0)
        curve["ret_sp500_1d"] = curve["equity_sp500_bh"].pct_change().fillna(0.0)
        curve["ret_cash_1d"] = curve["equity_cash_fedfunds"].pct_change().fillna(0.0)
        curve["drawdown_strategy"] = curve["equity_strategy"] / curve["equity_strategy"].cummax() - 1.0
        curve["drawdown_sp500"] = curve["equity_sp500_bh"] / curve["equity_sp500_bh"].cummax() - 1.0
        curve["drawdown_cash"] = curve["equity_cash_fedfunds"] / curve["equity_cash_fedfunds"].cummax() - 1.0
        curve.to_parquet(OUT_CURVE, index=False)
        pd.DataFrame(ledger).to_parquet(OUT_LEDGER, index=False)

        t122 = pd.read_parquet(IN_T122_CURVE).copy()
        t122["date"] = pd.to_datetime(t122["date"], errors="coerce").dt.normalize()
        reg = curve[["date", "split", "equity_strategy", "n_selected"]].merge(
            t122[["date", "split", "equity_strategy", "n_selected"]],
            on="date",
            how="left",
            suffixes=("_t126", "_t122"),
        )
        reg["abs_diff_equity"] = (reg["equity_strategy_t126"] - reg["equity_strategy_t122"]).abs()
        baseline_reg = {
            "rows_t126": int(len(curve)),
            "rows_t122": int(len(t122)),
            "rows_joined": int(len(reg)),
            "max_abs_diff_equity": float(reg["abs_diff_equity"].max()),
            "mean_abs_diff_equity": float(reg["abs_diff_equity"].mean()),
            "equity_end_t126": float(curve["equity_strategy"].iloc[-1]),
            "equity_end_t122": float(t122["equity_strategy"].iloc[-1]) if len(t122) else None,
            "n_selected_equal_ratio": float(np.mean(reg["n_selected_t126"] == reg["n_selected_t122"])) if len(reg) else 0.0,
        }
        write_json(OUT_BASELINE_REG, baseline_reg)

        timing_ref = pd.read_parquet(IN_T125_TIMING).copy()
        timing_ref["date"] = pd.to_datetime(timing_ref["date"], errors="coerce").dt.normalize()
        sig_all = pd.read_parquet(IN_T125_SIGNALS).copy()
        sig_all["date"] = pd.to_datetime(sig_all["date"], errors="coerce").dt.normalize()
        timing = sig_all[["date", "split", "state_cash"]].merge(macro[["date", "sp500_close", "fed_funds_rate"]], on="date", how="left")
        timing["sp500_close"] = pd.to_numeric(timing["sp500_close"], errors="coerce").ffill().bfill()
        timing["fed_funds_rate"] = pd.to_numeric(timing["fed_funds_rate"], errors="coerce").ffill().bfill()
        timing["cash_ret"] = np.log1p((timing["fed_funds_rate"] / 100.0) / 252.0)
        timing["sp500_ret"] = timing["sp500_close"].pct_change().fillna(0.0)
        timing["strategy_ret"] = np.where(timing["state_cash"].astype(int) == 1, timing["cash_ret"], timing["sp500_ret"])
        timing["equity"] = INITIAL_CAPITAL * (1.0 + pd.to_numeric(timing["strategy_ret"], errors="coerce").fillna(0.0)).cumprod()
        timing["drawdown"] = timing["equity"] / timing["equity"].cummax() - 1.0
        tr = timing.merge(timing_ref[["date", "strategy_ret", "equity", "drawdown"]], on="date", how="inner", suffixes=("_new", "_t125"))
        trigger_reg = {
            "rows_new": int(len(timing)),
            "rows_ref_t125": int(len(timing_ref)),
            "rows_joined": int(len(tr)),
            "max_abs_diff_strategy_ret": float((tr["strategy_ret_new"] - tr["strategy_ret_t125"]).abs().max()) if len(tr) else None,
            "max_abs_diff_equity": float((tr["equity_new"] - tr["equity_t125"]).abs().max()) if len(tr) else None,
            "max_abs_diff_drawdown": float((tr["drawdown_new"] - tr["drawdown_t125"]).abs().max()) if len(tr) else None,
        }
        write_json(OUT_TRIGGER_REG, trigger_reg)

        train = curve[curve["split"] == "TRAIN"].copy()
        hold = curve[curve["split"] == "HOLDOUT"].copy()
        acid = curve[(curve["date"] >= ACID_US_START) & (curve["date"] <= ACID_US_END)].copy()
        metrics = {
            "integrated_strategy": {
                "train": equity_metrics(train, "equity_strategy"),
                "holdout": equity_metrics(hold, "equity_strategy"),
                "acid_us": equity_metrics(acid, "equity_strategy"),
                "cash_frac_train": float(train["state_cash"].mean()) if len(train) else 0.0,
                "cash_frac_holdout": float(hold["state_cash"].mean()) if len(hold) else 0.0,
                "switches_total": int(count_switches(curve["state_cash"])),
                "total_cost_paid": float(curve["cost_paid"].sum()),
            },
            "sp500_bh": {
                "train": equity_metrics(train, "equity_sp500_bh"),
                "holdout": equity_metrics(hold, "equity_sp500_bh"),
                "acid_us": equity_metrics(acid, "equity_sp500_bh"),
            },
            "cash_fedfunds": {
                "train": equity_metrics(train, "equity_cash_fedfunds"),
                "holdout": equity_metrics(hold, "equity_cash_fedfunds"),
                "acid_us": equity_metrics(acid, "equity_cash_fedfunds"),
            },
            "t122_reference": {
                "train": equity_metrics(t122[t122["split"] == "TRAIN"], "equity_strategy"),
                "holdout": equity_metrics(t122[t122["split"] == "HOLDOUT"], "equity_strategy"),
                "acid_us": equity_metrics(
                    t122[
                        (pd.to_datetime(t122["date"]).dt.normalize() >= ACID_US_START)
                        & (pd.to_datetime(t122["date"]).dt.normalize() <= ACID_US_END)
                    ],
                    "equity_strategy",
                ),
            },
        }
        if IN_T115_CURVE.exists():
            t115 = pd.read_parquet(IN_T115_CURVE).copy()
            t115["date"] = pd.to_datetime(t115["date"], errors="coerce").dt.normalize()
            metrics["t115_reference"] = {
                "train": equity_metrics(t115[t115["split"] == "TRAIN"], "equity"),
                "holdout": equity_metrics(t115[t115["split"] == "HOLDOUT"], "equity"),
                "acid_us": equity_metrics(
                    t115[
                        (pd.to_datetime(t115["date"]).dt.normalize() >= ACID_US_START)
                        & (pd.to_datetime(t115["date"]).dt.normalize() <= ACID_US_END)
                    ],
                    "equity",
                ),
            }
        write_json(OUT_METRICS, metrics)

        hold_mdd = float(metrics["integrated_strategy"]["holdout"]["mdd"])
        mdd_check = {
            "hard_constraint": "MDD_HOLDOUT >= -0.15",
            "mdd_holdout_integrated": hold_mdd,
            "passes_hard_constraint": bool(hold_mdd >= -0.15),
            "note": "Informativo para decisão de produto; não bloqueia PASS técnico da execução.",
        }
        write_json(OUT_MDD_CHECK, mdd_check)

        summary = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "config": {
                "top_n": top_n,
                "cadence_days": cadence_days,
                "cost_rate_one_way": cost_rate,
                "trigger_winner": trig_winner,
                "trigger_threshold": thr,
                "h_in": h_in,
                "h_out": h_out,
            },
            "metrics": metrics,
            "mdd_hard_constraint_check": mdd_check,
            "regressions": {"t122": baseline_reg, "t125_timing": trigger_reg},
        }
        write_json(OUT_SUMMARY, summary)

        write_json(
            OUT_PREFLIGHT,
            {
                "inputs_present": {
                    "T120_scores": IN_SCORES.exists(),
                    "SSOT_US": IN_SSOT_US.exists(),
                    "SSOT_MACRO": IN_MACRO.exists(),
                    "US_UNIVERSE": IN_UNIVERSE.exists(),
                    "T122_CFG": IN_T122_CFG.exists(),
                    "T122_CURVE": IN_T122_CURVE.exists(),
                    "T125_SIGNALS": IN_T125_SIGNALS.exists(),
                    "T125_CFG": IN_T125_CFG.exists(),
                    "T125_TIMING": IN_T125_TIMING.exists(),
                    "T115_CURVE": IN_T115_CURVE.exists(),
                },
                "sim_dates": {
                    "n_rows": len(sim_dates),
                    "min": str(sim_dates[0].date()) if sim_dates else None,
                    "max": str(sim_dates[-1].date()) if sim_dates else None,
                },
                "config_loaded": {"top_n": top_n, "cadence_days": cadence_days, "cost_rate_one_way": cost_rate},
                "trigger_loaded": {"winner": trig_winner, "threshold": thr, "h_in": h_in, "h_out": h_out},
            },
        )
        write_json(
            OUT_JOIN,
            {
                "sim_rows_expected": len(sim_dates),
                "joined_rows": len(sig_sim),
                "join_coverage_ratio": float(len(sig_sim) / max(len(sim_dates), 1)),
                "state_cash_nan_count": int(sig_sim["state_cash"].isna().sum()),
                "state_cash_unique": sorted(pd.to_numeric(sig_sim["state_cash"], errors="coerce").dropna().astype(int).unique().tolist()),
                "split_counts_curve": curve["split"].value_counts().to_dict(),
            },
        )

        base = curve.iloc[0]
        norm_strat = 100.0 * curve["equity_strategy"] / float(base["equity_strategy"])
        norm_sp = 100.0 * curve["equity_sp500_bh"] / float(base["equity_sp500_bh"])
        norm_cash = 100.0 * curve["equity_cash_fedfunds"] / float(base["equity_cash_fedfunds"])
        t122_m = t122[["date", "equity_strategy"]].copy()
        t122_m = t122_m.rename(columns={"equity_strategy": "equity_t122"}).sort_values("date")
        plt_df = curve.merge(t122_m, on="date", how="left")
        norm_t122 = 100.0 * plt_df["equity_t122"] / float(plt_df["equity_t122"].iloc[0])

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Equity Normalizado (Integrado vs SP500 vs T122 vs Cash)",
                "Drawdown Comparativo",
                "Estado de Caixa (Trigger)",
                "Switches / Cash Frac por Split",
            ),
            specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "xy"}]],
            horizontal_spacing=0.08,
            vertical_spacing=0.12,
        )
        fig.add_trace(go.Scatter(x=curve["date"], y=norm_strat, mode="lines", name="T126 Integrado"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve["date"], y=norm_sp, mode="lines", name="SP500 B&H"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve["date"], y=norm_t122, mode="lines", name="T122 Sem Trigger"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve["date"], y=norm_cash, mode="lines", name="Cash FedFunds"), row=1, col=1)

        fig.add_trace(go.Scatter(x=curve["date"], y=curve["drawdown_strategy"], mode="lines", name="DD T126"), row=1, col=2)
        fig.add_trace(go.Scatter(x=curve["date"], y=curve["drawdown_sp500"], mode="lines", name="DD SP500"), row=1, col=2)
        fig.add_trace(go.Scatter(x=curve["date"], y=curve["drawdown_cash"], mode="lines", name="DD Cash"), row=1, col=2)

        fig.add_trace(go.Scatter(x=curve["date"], y=curve["state_cash"], mode="lines", name="state_cash"), row=2, col=1)
        switches_train = count_switches(train["state_cash"])
        switches_hold = count_switches(hold["state_cash"])
        cash_frac_train = float(train["state_cash"].mean()) if len(train) else 0.0
        cash_frac_hold = float(hold["state_cash"].mean()) if len(hold) else 0.0
        fig.add_trace(
            go.Bar(
                x=["TRAIN", "HOLDOUT", "TRAIN", "HOLDOUT"],
                y=[switches_train, switches_hold, cash_frac_train, cash_frac_hold],
                name="Switches/CashFrac",
            ),
            row=2,
            col=2,
        )
        fig.update_layout(height=900, width=1450, title=f"{RUN_ID} - integrated backtest", legend=dict(orientation="h"))
        fig.write_html(OUT_PLOT, include_plotlyjs="cdn")

        outputs_expected = [
            OUT_SCRIPT,
            OUT_CURVE,
            OUT_LEDGER,
            OUT_SUMMARY,
            OUT_PLOT,
            OUT_REPORT,
            OUT_PREFLIGHT,
            OUT_JOIN,
            OUT_BASELINE_REG,
            OUT_TRIGGER_REG,
            OUT_METRICS,
            OUT_MDD_CHECK,
        ]
        outputs_ok = all(p.exists() for p in outputs_expected if p != OUT_REPORT)
        gates.append(
            Gate(
                "G_OUTPUTS_PRESENT",
                outputs_ok and len(curve) == EXPECTED_ROWS and set(curve["state_cash"].unique()).issubset({0, 1}),
                f"curve_rows={len(curve)} expected={EXPECTED_ROWS} state_unique={sorted(curve['state_cash'].unique().tolist())}",
            )
        )

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, "mode=idempotent"))

        inputs = [
            str(IN_SCORES.relative_to(ROOT)),
            str(IN_SSOT_US.relative_to(ROOT)),
            str(IN_MACRO.relative_to(ROOT)),
            str(IN_UNIVERSE.relative_to(ROOT)),
            str(IN_T122_CFG.relative_to(ROOT)),
            str(IN_T122_CURVE.relative_to(ROOT)),
            str(IN_T125_SIGNALS.relative_to(ROOT)),
            str(IN_T125_CFG.relative_to(ROOT)),
            str(IN_T125_TIMING.relative_to(ROOT)),
            str(CHANGELOG_PATH.relative_to(ROOT)),
        ]
        if IN_T115_CURVE.exists():
            inputs.append(str(IN_T115_CURVE.relative_to(ROOT)))

        outputs = [
            str(OUT_SCRIPT.relative_to(ROOT)),
            str(OUT_CURVE.relative_to(ROOT)),
            str(OUT_LEDGER.relative_to(ROOT)),
            str(OUT_SUMMARY.relative_to(ROOT)),
            str(OUT_PLOT.relative_to(ROOT)),
            str(OUT_REPORT.relative_to(ROOT)),
            str(OUT_PREFLIGHT.relative_to(ROOT)),
            str(OUT_JOIN.relative_to(ROOT)),
            str(OUT_BASELINE_REG.relative_to(ROOT)),
            str(OUT_TRIGGER_REG.relative_to(ROOT)),
            str(OUT_METRICS.relative_to(ROOT)),
            str(OUT_MDD_CHECK.relative_to(ROOT)),
        ]

        provisional_gates = gates + [
            Gate("Gx_HASH_MANIFEST_PRESENT", True, f"path={OUT_MANIFEST.relative_to(ROOT)}"),
            Gate("G_SHA256_INTEGRITY_SELF_CHECK", True, "mismatches=0 (provisional)"),
        ]
        if any(not g.passed for g in provisional_gates):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(make_report(provisional_gates, retry_log, artifacts, status_txt), encoding="utf-8")

        hash_targets = [CHANGELOG_PATH] + [ROOT / p for p in outputs]
        hashes: dict[str, str] = {}
        for p in hash_targets:
            if p.exists():
                hashes[str(p.relative_to(ROOT))] = sha256_file(p)
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "policy": "no_self_hash",
            "generated_at_utc": pd.Timestamp.now("UTC").isoformat(),
            "inputs_consumed": inputs,
            "outputs_produced": outputs,
            "hashes_sha256": hashes,
        }
        write_json(OUT_MANIFEST, manifest)

        mm = 0
        for rp, hv in hashes.items():
            p = ROOT / rp
            if (not p.exists()) or (sha256_file(p) != hv):
                mm += 1
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST.relative_to(ROOT)}"))
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", mm == 0, f"mismatches={mm}"))
        if any(not g.passed for g in gates):
            overall_pass = False
        status_txt = "PASS" if overall_pass else "FAIL"
        OUT_REPORT.write_text(make_report(gates, retry_log, artifacts, status_txt), encoding="utf-8")

        hashes[str(OUT_REPORT.relative_to(ROOT))] = sha256_file(OUT_REPORT)
        manifest["hashes_sha256"] = hashes
        manifest["generated_at_utc"] = pd.Timestamp.now("UTC").isoformat()
        write_json(OUT_MANIFEST, manifest)

    except Exception as e:
        overall_pass = False
        retry_log.append(f"{type(e).__name__}: {e}")
        gates.append(Gate("G_FATAL", False, retry_log[-1]))
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(make_report(gates, retry_log, artifacts, "FAIL"), encoding="utf-8")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
