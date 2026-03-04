#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T115"
RUN_ID = "T115-PHASE9D-US-BACKTEST-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"

IN_PRED = ROOT / "src/data_engine/features/T114_US_ML_PREDICTIONS_DAILY.parquet"
IN_CFG = ROOT / "src/data_engine/features/T114_US_ML_SELECTED_CONFIG.json"
IN_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO_EXPANDED.parquet"

OUT_SCRIPT = ROOT / "scripts/t115_backtest_us_factory_m3_ml_v1.py"
OUT_CURVE = ROOT / "src/data_engine/portfolio/T115_US_FACTORY_CURVE_DAILY.parquet"
OUT_BH = ROOT / "src/data_engine/portfolio/T115_US_FACTORY_BASELINE_SP500_BUYHOLD_DAILY.parquet"
OUT_CASH = ROOT / "src/data_engine/portfolio/T115_US_FACTORY_BASELINE_CASH_FEDFUNDS_DAILY.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T115_US_FACTORY_SUMMARY.json"
OUT_HTML = ROOT / "outputs/plots/T115_STATE3_PHASE9D_US_FACTORY_BACKTEST.html"
OUT_REPORT = ROOT / "outputs/governanca/T115-PHASE9D-US-BACKTEST-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T115-PHASE9D-US-BACKTEST-V1_manifest.json"
OUT_EVID = ROOT / "outputs/governanca/T115-PHASE9D-US-BACKTEST-V1_evidence"
OUT_PREFLIGHT = OUT_EVID / "input_preflight.json"
OUT_DUAL_ACID = OUT_EVID / "dual_acid_metrics.json"
OUT_SWITCH_COST = OUT_EVID / "switch_and_cost_audit.json"
OUT_JOIN = OUT_EVID / "join_coverage.json"

RECORTE_START = pd.Timestamp("2018-07-02")
RECORTE_END = pd.Timestamp("2026-02-26")
TRAIN_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-02")
EXPECTED_TOTAL = 1902
EXPECTED_TRAIN = 1115
EXPECTED_HOLDOUT = 787
COST_ONE_WAY = 0.0001  # 1bp

ACID_BR_START = pd.Timestamp("2024-11-01")
ACID_BR_END = pd.Timestamp("2025-11-30")
ACID_US_START = pd.Timestamp("2025-03-06")
ACID_US_END = pd.Timestamp("2025-05-09")

TRACEABILITY_LINE = "- 2026-03-04T00:00:00Z | EXEC: T115 Backtest isolado Fábrica US (S&P 500 USD + tank Fed funds + custo 1bp em switches) consumindo T114 state_cash e reportando dual acid window (BR+US). Artefatos: scripts/t115_backtest_us_factory_m3_ml_v1.py; src/data_engine/portfolio/T115_US_FACTORY_{CURVE_DAILY,BASELINE_SP500_BUYHOLD_DAILY,BASELINE_CASH_FEDFUNDS_DAILY}.parquet; src/data_engine/portfolio/T115_US_FACTORY_SUMMARY.json; outputs/plots/T115_STATE3_PHASE9D_US_FACTORY_BACKTEST.html; outputs/governanca/T115-PHASE9D-US-BACKTEST-V1_{report,manifest}.md"


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


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
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    if pd.isna(obj):
        return None
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_changelog_one_line_idempotent(line: str) -> bool:
    existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    if line in existing:
        return True
    text = existing
    if text and not text.endswith("\n"):
        text += "\n"
    text += line.rstrip("\n") + "\n"
    CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return line in CHANGELOG_PATH.read_text(encoding="utf-8")


def compute_mdd(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").to_numpy(dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return float(np.min(dd))


def compute_sharpe(ret_1d: pd.Series) -> float:
    r = pd.to_numeric(ret_1d, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(r) < 2:
        return 0.0
    std = float(np.std(r, ddof=1))
    if std <= 0:
        return 0.0
    return float((np.mean(r) / std) * np.sqrt(252.0))


def compute_cagr(equity: pd.Series) -> float:
    eq = pd.to_numeric(equity, errors="coerce").to_numpy(dtype=float)
    if len(eq) < 2 or eq[0] <= 0:
        return 0.0
    years = len(eq) / 252.0
    if years <= 0:
        return 0.0
    return float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0)


def count_switches(state_cash: pd.Series) -> int:
    return int((state_cash.astype(int).diff().abs() == 1).sum())


def subset_metrics(df: pd.DataFrame, prefix: str) -> dict[str, float]:
    if len(df) == 0:
        return {
            f"rows_{prefix}": 0,
            f"equity_end_{prefix}": 100000.0,
            f"mdd_{prefix}": 0.0,
            f"sharpe_{prefix}": 0.0,
            f"cagr_{prefix}": 0.0,
            f"cash_frac_{prefix}": 0.0,
            f"switches_{prefix}": 0,
        }
    ret = pd.to_numeric(df["strategy_ret_adj"], errors="coerce").fillna(0.0)
    eq = 100000.0 * (1.0 + ret).cumprod()
    return {
        f"rows_{prefix}": int(len(df)),
        f"equity_end_{prefix}": float(eq.iloc[-1]),
        f"mdd_{prefix}": compute_mdd(eq),
        f"sharpe_{prefix}": compute_sharpe(ret),
        f"cagr_{prefix}": compute_cagr(eq),
        f"cash_frac_{prefix}": float(df["state_cash"].mean()),
        f"switches_{prefix}": int(count_switches(df["state_cash"])),
    }


def render_report(gates: list[Gate], retry_log: list[str], overall: bool, summary: dict[str, Any]) -> str:
    lines = [f"# HEADER: {TASK_ID}", "", "## STEP GATES"]
    for g in gates:
        lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
    lines.extend(
        [
            "",
            "## RESUMO",
            (
                f"- HOLDOUT strategy: equity={summary.get('equity_end_holdout', 0.0):.2f} "
                f"mdd={summary.get('mdd_holdout', 0.0):.4f} sharpe={summary.get('sharpe_holdout', 0.0):.4f}"
            ),
            (
                f"- HOLDOUT baseline_sp500: equity={summary.get('equity_end_sp500_holdout', 0.0):.2f} "
                f"mdd={summary.get('mdd_sp500_holdout', 0.0):.4f} sharpe={summary.get('sharpe_sp500_holdout', 0.0):.4f}"
            ),
            (
                f"- HOLDOUT baseline_cash: equity={summary.get('equity_end_cash_holdout', 0.0):.2f} "
                f"mdd={summary.get('mdd_cash_holdout', 0.0):.4f} sharpe={summary.get('sharpe_cash_holdout', 0.0):.4f}"
            ),
            "",
            "## RETRY LOG",
            "- none" if not retry_log else "",
        ]
    )
    if retry_log:
        for r in retry_log:
            lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## ARTIFACT LINKS",
            f"- {OUT_CURVE.relative_to(ROOT)}",
            f"- {OUT_BH.relative_to(ROOT)}",
            f"- {OUT_CASH.relative_to(ROOT)}",
            f"- {OUT_SUMMARY.relative_to(ROOT)}",
            f"- {OUT_HTML.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_PREFLIGHT.relative_to(ROOT)}",
            f"- {OUT_DUAL_ACID.relative_to(ROOT)}",
            f"- {OUT_SWITCH_COST.relative_to(ROOT)}",
            f"- {OUT_JOIN.relative_to(ROOT)}",
            "",
            f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    summary: dict[str, Any] = {}
    try:
        for p in [
            OUT_CURVE,
            OUT_BH,
            OUT_CASH,
            OUT_SUMMARY,
            OUT_HTML,
            OUT_REPORT,
            OUT_MANIFEST,
            OUT_PREFLIGHT,
            OUT_DUAL_ACID,
            OUT_SWITCH_COST,
            OUT_JOIN,
        ]:
            p.parent.mkdir(parents=True, exist_ok=True)

        env_ok = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", env_ok, f"python={sys.executable}"))
        if not env_ok:
            raise RuntimeError("python env check failed")

        inputs_ok = IN_PRED.exists() and IN_CFG.exists() and IN_MACRO.exists()
        gates.append(
            Gate(
                "G0_INPUTS_EXIST",
                inputs_ok,
                f"pred={IN_PRED.exists()} cfg={IN_CFG.exists()} macro={IN_MACRO.exists()}",
            )
        )
        if not inputs_ok:
            raise RuntimeError("required inputs missing")

        pred = pd.read_parquet(IN_PRED).copy()
        macro = pd.read_parquet(IN_MACRO).copy()
        cfg = json.loads(IN_CFG.read_text(encoding="utf-8"))
        pred["date"] = pd.to_datetime(pred["date"]).dt.normalize()
        macro["date"] = pd.to_datetime(macro["date"]).dt.normalize()
        pred = pred[(pred["date"] >= RECORTE_START) & (pred["date"] <= RECORTE_END)].sort_values("date").reset_index(drop=True)
        rows_ok = len(pred) == EXPECTED_TOTAL
        split_ok = int((pred["split"] == "TRAIN").sum()) == EXPECTED_TRAIN and int((pred["split"] == "HOLDOUT").sum()) == EXPECTED_HOLDOUT
        gates.append(Gate("G1_PRED_SCOPE_SPLIT_OK", rows_ok and split_ok, f"rows={len(pred)}"))
        if not (rows_ok and split_ok):
            raise RuntimeError("pred scope/split mismatch")

        if "fed_funds_rate" not in macro.columns:
            raise RuntimeError("fed_funds_rate missing in macro")
        join = pred.merge(macro[["date", "fed_funds_rate"]], on="date", how="inner")
        join_ok = len(join) == EXPECTED_TOTAL
        write_json(
            OUT_JOIN,
            {
                "rows_left_pred": len(pred),
                "rows_right_macro": len(macro),
                "rows_joined": len(join),
                "expected_joined_rows": EXPECTED_TOTAL,
                "date_min": join["date"].min(),
                "date_max": join["date"].max(),
                "acid_br_all_holdout": bool(
                    (join[(join["date"] >= ACID_BR_START) & (join["date"] <= ACID_BR_END)]["split"] == "HOLDOUT").all()
                ),
                "acid_us_all_holdout": bool(
                    (join[(join["date"] >= ACID_US_START) & (join["date"] <= ACID_US_END)]["split"] == "HOLDOUT").all()
                ),
            },
        )
        gates.append(Gate("G2_JOIN_COVERAGE_OK", join_ok, f"joined={len(join)}"))
        if not join_ok:
            raise RuntimeError("join coverage mismatch")

        join["sp500_ret_1d_recalc"] = pd.to_numeric(join["sp500_close"], errors="coerce").pct_change().fillna(0.0)
        ret_nan_ok = not join["sp500_ret_1d_recalc"].isna().any() and float(join["sp500_ret_1d_recalc"].iloc[0]) == 0.0
        gates.append(Gate("G3_MARKET_RET_OK", ret_nan_ok, f"first_ret={join['sp500_ret_1d_recalc'].iloc[0]:.6f}"))
        if not ret_nan_ok:
            raise RuntimeError("market return invalid")

        join["fed_funds_rate"] = pd.to_numeric(join["fed_funds_rate"], errors="coerce")
        ff_ok = not join["fed_funds_rate"].isna().any()
        gates.append(Gate("G4_FEDFUNDS_NO_NAN", ff_ok, f"nan_count={int(join['fed_funds_rate'].isna().sum())}"))
        if not ff_ok:
            raise RuntimeError("fed_funds_rate contains NaN")

        join["cash_ret_1d"] = (1.0 + join["fed_funds_rate"] / 100.0) ** (1.0 / 252.0) - 1.0
        join["state_cash"] = pd.to_numeric(join["state_cash"], errors="coerce").fillna(0).astype(int).clip(0, 1)
        join["switch_flag"] = (join["state_cash"].diff().abs() == 1).astype(int)
        join["strategy_ret_raw"] = np.where(join["state_cash"] == 1, join["cash_ret_1d"], join["sp500_ret_1d_recalc"])
        join["cost_applied"] = join["switch_flag"] * COST_ONE_WAY
        join["strategy_ret_adj"] = join["strategy_ret_raw"] - join["cost_applied"]
        join["equity_strategy"] = 100000.0 * (1.0 + join["strategy_ret_adj"]).cumprod()
        join["equity_sp500"] = 100000.0 * (1.0 + join["sp500_ret_1d_recalc"]).cumprod()
        join["equity_cash"] = 100000.0 * (1.0 + join["cash_ret_1d"]).cumprod()

        switch_rows = join[join["switch_flag"] == 1].copy()
        write_json(
            OUT_SWITCH_COST,
            {
                "cost_one_way": COST_ONE_WAY,
                "total_switches": int(len(switch_rows)),
                "total_cost_paid": float(join["cost_applied"].sum()),
                "examples_first_5": switch_rows[
                    ["date", "state_cash", "strategy_ret_raw", "cost_applied", "strategy_ret_adj"]
                ].head(5).to_dict(orient="records"),
            },
        )
        gates.append(Gate("G5_SWITCH_COST_AUDIT_READY", OUT_SWITCH_COST.exists(), f"switches={len(switch_rows)}"))

        strategy_curve = join[
            [
                "date",
                "split",
                "state_cash",
                "switch_flag",
                "cost_applied",
                "strategy_ret_adj",
                "equity_strategy",
                "sp500_ret_1d_recalc",
                "cash_ret_1d",
            ]
        ].rename(columns={"strategy_ret_adj": "ret_1d", "equity_strategy": "equity"})
        baseline_sp500 = join[["date", "split", "sp500_ret_1d_recalc", "equity_sp500"]].rename(
            columns={"sp500_ret_1d_recalc": "ret_1d", "equity_sp500": "equity"}
        )
        baseline_cash = join[["date", "split", "cash_ret_1d", "equity_cash"]].rename(
            columns={"cash_ret_1d": "ret_1d", "equity_cash": "equity"}
        )

        strategy_curve.to_parquet(OUT_CURVE, index=False)
        baseline_sp500.to_parquet(OUT_BH, index=False)
        baseline_cash.to_parquet(OUT_CASH, index=False)
        outputs_ok = OUT_CURVE.exists() and OUT_BH.exists() and OUT_CASH.exists()
        gates.append(Gate("G6_PARQUETS_WRITTEN", outputs_ok, f"curve={outputs_ok}"))
        if not outputs_ok:
            raise RuntimeError("parquet outputs missing")

        train_mask = join["split"] == "TRAIN"
        hold_mask = join["split"] == "HOLDOUT"
        metrics_train = subset_metrics(join.loc[train_mask].copy(), "train")
        metrics_hold = subset_metrics(join.loc[hold_mask].copy(), "holdout")
        metrics_all = subset_metrics(join.copy(), "all")

        def baseline_metrics(df: pd.DataFrame, ret_col: str, prefix: str) -> dict[str, float]:
            ret = pd.to_numeric(df[ret_col], errors="coerce").fillna(0.0)
            eq = 100000.0 * (1.0 + ret).cumprod()
            return {
                f"equity_end_{prefix}": float(eq.iloc[-1]) if len(eq) else 100000.0,
                f"mdd_{prefix}": compute_mdd(eq),
                f"sharpe_{prefix}": compute_sharpe(ret),
                f"cagr_{prefix}": compute_cagr(eq),
            }

        sp_hold = baseline_metrics(join.loc[hold_mask].copy(), "sp500_ret_1d_recalc", "sp500_holdout")
        cash_hold = baseline_metrics(join.loc[hold_mask].copy(), "cash_ret_1d", "cash_holdout")

        acid_br = join[(join["date"] >= ACID_BR_START) & (join["date"] <= ACID_BR_END)].copy()
        acid_us = join[(join["date"] >= ACID_US_START) & (join["date"] <= ACID_US_END)].copy()

        def window_metrics(df: pd.DataFrame, name: str) -> dict[str, Any]:
            if len(df) == 0:
                return {"window": name, "rows": 0}
            strat = subset_metrics(df.copy(), "strategy")
            sp = baseline_metrics(df.copy(), "sp500_ret_1d_recalc", "sp500")
            ca = baseline_metrics(df.copy(), "cash_ret_1d", "cash")
            return {"window": name, "rows": int(len(df)), **strat, **sp, **ca}

        dual_acid = {
            "acid_br": {"start": ACID_BR_START, "end": ACID_BR_END, **window_metrics(acid_br, "acid_br")},
            "acid_us": {"start": ACID_US_START, "end": ACID_US_END, **window_metrics(acid_us, "acid_us")},
        }
        write_json(OUT_DUAL_ACID, dual_acid)
        acid_ok = int(dual_acid["acid_br"]["rows"]) > 0 and int(dual_acid["acid_us"]["rows"]) > 0
        gates.append(
            Gate(
                "G7_DUAL_ACID_READY",
                acid_ok,
                f"acid_br_rows={dual_acid['acid_br']['rows']} acid_us_rows={dual_acid['acid_us']['rows']}",
            )
        )
        if not acid_ok:
            raise RuntimeError("dual acid windows empty")

        summary = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "winner_from_t114": cfg.get("winner", {}),
            "execution_convention": "state_cash[t] aplica retorno close-to-close de t (proba de t derivada de features shift(1), equivalente operacional a decisão no close de t-1).",
            **metrics_train,
            **metrics_hold,
            **metrics_all,
            **sp_hold,
            **cash_hold,
            "total_switches": int(len(switch_rows)),
            "total_cost_paid": float(join["cost_applied"].sum()),
            "cost_one_way": COST_ONE_WAY,
        }
        write_json(OUT_SUMMARY, summary)
        write_json(
            OUT_PREFLIGHT,
            {
                "pred_rows": len(pred),
                "macro_rows": len(macro),
                "joined_rows": len(join),
                "date_min": join["date"].min(),
                "date_max": join["date"].max(),
                "train_rows": int(train_mask.sum()),
                "holdout_rows": int(hold_mask.sum()),
                "expected_rows": EXPECTED_TOTAL,
                "expected_train": EXPECTED_TRAIN,
                "expected_holdout": EXPECTED_HOLDOUT,
            },
        )
        gates.append(Gate("G8_SUMMARY_PREFLIGHT_WRITTEN", OUT_SUMMARY.exists() and OUT_PREFLIGHT.exists(), "summary+preflight"))

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
            subplot_titles=("Equity Comparison (USD)", "Drawdown Comparison", "Holdout Metrics"),
        )
        fig.add_trace(go.Scatter(x=join["date"], y=join["equity_strategy"], name="US Factory Strategy"), row=1, col=1)
        fig.add_trace(go.Scatter(x=join["date"], y=join["equity_sp500"], name="SP500 BuyHold"), row=1, col=1)
        fig.add_trace(go.Scatter(x=join["date"], y=join["equity_cash"], name="Cash FedFunds"), row=1, col=1)
        dd_s = join["equity_strategy"] / join["equity_strategy"].cummax() - 1.0
        dd_b = join["equity_sp500"] / join["equity_sp500"].cummax() - 1.0
        dd_c = join["equity_cash"] / join["equity_cash"].cummax() - 1.0
        fig.add_trace(go.Scatter(x=join["date"], y=dd_s, name="DD Strategy"), row=2, col=1)
        fig.add_trace(go.Scatter(x=join["date"], y=dd_b, name="DD SP500"), row=2, col=1)
        fig.add_trace(go.Scatter(x=join["date"], y=dd_c, name="DD Cash"), row=2, col=1)
        fig.add_hline(y=-0.10, line_dash="dash", line_color="red", row=2, col=1)

        arr = join["state_cash"].to_numpy(dtype=int)
        seg_start = None
        for i, val in enumerate(arr):
            if val == 1 and seg_start is None:
                seg_start = i
            if val == 0 and seg_start is not None:
                fig.add_vrect(
                    x0=join["date"].iloc[seg_start],
                    x1=join["date"].iloc[i - 1],
                    fillcolor="orange",
                    opacity=0.12,
                    line_width=0,
                    row=1,
                    col=1,
                )
                seg_start = None
        if seg_start is not None:
            fig.add_vrect(
                x0=join["date"].iloc[seg_start],
                x1=join["date"].iloc[-1],
                fillcolor="orange",
                opacity=0.12,
                line_width=0,
                row=1,
                col=1,
            )

        tbl_header = ["Metric", "Strategy HOLDOUT", "SP500 HOLDOUT", "Cash HOLDOUT"]
        tbl_vals = [
            ["Equity End", "MDD", "Sharpe", "CAGR", "Cash Frac", "Switches"],
            [
                f"{summary['equity_end_holdout']:.2f}",
                f"{summary['mdd_holdout']:.4f}",
                f"{summary['sharpe_holdout']:.4f}",
                f"{summary['cagr_holdout']:.4f}",
                f"{summary['cash_frac_holdout']:.4f}",
                str(summary["switches_holdout"]),
            ],
            [
                f"{summary['equity_end_sp500_holdout']:.2f}",
                f"{summary['mdd_sp500_holdout']:.4f}",
                f"{summary['sharpe_sp500_holdout']:.4f}",
                f"{summary['cagr_sp500_holdout']:.4f}",
                "-",
                "-",
            ],
            [
                f"{summary['equity_end_cash_holdout']:.2f}",
                f"{summary['mdd_cash_holdout']:.4f}",
                f"{summary['sharpe_cash_holdout']:.4f}",
                f"{summary['cagr_cash_holdout']:.4f}",
                "-",
                "-",
            ],
        ]
        fig.add_trace(go.Table(header={"values": tbl_header}, cells={"values": tbl_vals}), row=3, col=1)
        fig.update_layout(height=1250, template="plotly_white", title="T115 - US Factory Isolated Backtest (USD)")
        fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")
        gates.append(Gate("G9_DASHBOARD_WRITTEN", OUT_HTML.exists(), f"path={OUT_HTML}"))

        ch_ok = append_changelog_one_line_idempotent(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"path={CHANGELOG_PATH}"))

        OUT_REPORT.write_text(render_report(gates, retry_log, all(g.passed for g in gates), summary), encoding="utf-8")

        hash_targets = [
            OUT_SCRIPT,
            OUT_CURVE,
            OUT_BH,
            OUT_CASH,
            OUT_SUMMARY,
            OUT_HTML,
            OUT_REPORT,
            OUT_PREFLIGHT,
            OUT_DUAL_ACID,
            OUT_SWITCH_COST,
            OUT_JOIN,
            CHANGELOG_PATH,
        ]
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "manifest_policy": "no_self_hash",
            "inputs_consumed": [
                str(IN_PRED.relative_to(ROOT)),
                str(IN_CFG.relative_to(ROOT)),
                str(IN_MACRO.relative_to(ROOT)),
            ],
            "outputs_produced": [
                str(OUT_SCRIPT.relative_to(ROOT)),
                str(OUT_CURVE.relative_to(ROOT)),
                str(OUT_BH.relative_to(ROOT)),
                str(OUT_CASH.relative_to(ROOT)),
                str(OUT_SUMMARY.relative_to(ROOT)),
                str(OUT_HTML.relative_to(ROOT)),
                str(OUT_REPORT.relative_to(ROOT)),
                str(OUT_MANIFEST.relative_to(ROOT)),
                str(OUT_PREFLIGHT.relative_to(ROOT)),
                str(OUT_DUAL_ACID.relative_to(ROOT)),
                str(OUT_SWITCH_COST.relative_to(ROOT)),
                str(OUT_JOIN.relative_to(ROOT)),
            ],
            "hashes_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in hash_targets},
        }
        write_json(OUT_MANIFEST, manifest)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST}"))

        mismatches = []
        for rel, exp in manifest["hashes_sha256"].items():
            got = sha256_file(ROOT / rel)
            if got != exp:
                mismatches.append(rel)
        hash_ok = len(mismatches) == 0
        gates.append(Gate("G_SHA256_INTEGRITY_SELF_CHECK", hash_ok, f"mismatches={len(mismatches)}"))

        overall = all(g.passed for g in gates)
        OUT_REPORT.write_text(render_report(gates, retry_log, overall, summary), encoding="utf-8")
        manifest["hashes_sha256"] = {str(p.relative_to(ROOT)): sha256_file(p) for p in hash_targets}
        write_json(OUT_MANIFEST, manifest)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        print("- none" if not retry_log else "\n".join(f"- {r}" for r in retry_log))
        print("ARTIFACT LINKS:")
        print(f"- {OUT_CURVE}")
        print(f"- {OUT_BH}")
        print(f"- {OUT_CASH}")
        print(f"- {OUT_SUMMARY}")
        print(f"- {OUT_HTML}")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print(f"- {OUT_PREFLIGHT}")
        print(f"- {OUT_DUAL_ACID}")
        print(f"- {OUT_SWITCH_COST}")
        print(f"- {OUT_JOIN}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2
    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(render_report(gates, retry_log, False, summary), encoding="utf-8")
        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        for r in retry_log:
            print(f"- {r}")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_REPORT}")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
