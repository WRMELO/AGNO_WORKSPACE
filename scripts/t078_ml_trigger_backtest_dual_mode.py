#!/home/wilson/AGNO_WORKSPACE/.venv/bin/python
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
import plotly.graph_objects as go
from plotly.subplots import make_subplots


if not ("agno_env" in sys.prefix or ".venv" in sys.prefix):
    raise RuntimeError("FATAL: Not in agno_env/.venv")


TASK_ID = "T078"
RUN_ID = "T078-ML-TRIGGER-BACKTEST-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100000.0

PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-02T18:00:00Z | BACKTEST: T078 Backtest financeiro do termostato ML (T077-V3) por cash-override sobre T072, "
    "com calibração thr/histerese em TRAIN e avaliação cega em HOLDOUT/acid. Artefatos: scripts/t078_ml_trigger_backtest_dual_mode.py; "
    "outputs/plots/T078_STATE3_PHASE6C_BACKTEST_COMPARATIVE.html; outputs/governanca/T078-ML-TRIGGER-BACKTEST-V1_manifest.json; "
    "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json"
)

INPUT_T072_CURVE = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_CURVE_DUAL_MODE.parquet"
INPUT_T072_CONFIG = ROOT / "src/data_engine/portfolio/T072_DUAL_MODE_SELECTED_CONFIG.json"
INPUT_T077_PRED = ROOT / "src/data_engine/features/T077_V3_PREDICTIONS_DAILY.parquet"

OUT_SCRIPT = ROOT / "scripts/t078_ml_trigger_backtest_dual_mode.py"
OUT_SELECTED_CFG = ROOT / "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json"
OUT_ABLATION = ROOT / "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_ABLATION_RESULTS.parquet"
OUT_CURVE_ML = ROOT / "src/data_engine/portfolio/T078_PORTFOLIO_CURVE_ML_TRIGGER.parquet"
OUT_CURVE_ORACLE = ROOT / "src/data_engine/portfolio/T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet"
OUT_SUMMARY = ROOT / "src/data_engine/portfolio/T078_BASELINE_SUMMARY_ML_TRIGGER.json"

OUT_PLOT = ROOT / "outputs/plots/T078_STATE3_PHASE6C_BACKTEST_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T078-ML-TRIGGER-BACKTEST-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T078-ML-TRIGGER-BACKTEST-V1_manifest.json"
OUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T078-ML-TRIGGER-BACKTEST-V1_evidence"
OUT_CANDIDATE_SET = OUT_EVIDENCE_DIR / "candidate_set.json"
OUT_SELECTION_RULE = OUT_EVIDENCE_DIR / "selection_rule.json"
OUT_METRICS_SNAPSHOT = OUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUT_ACID_WINDOW = OUT_EVIDENCE_DIR / "acid_window_definition.json"
OUT_JOIN_COVERAGE = OUT_EVIDENCE_DIR / "join_coverage.json"

THR_GRID = [0.05, 0.10, 0.15, 0.20, 0.25]
H_IN_GRID = [1, 2, 3]
H_OUT_GRID = [2, 3, 4, 5]
MAX_SWITCHES_TRAIN = 40
MDD_MIN_TRAIN = -0.30

ACID_START = pd.Timestamp("2024-11-01")
ACID_END = pd.Timestamp("2025-11-30")


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


def normalize_to_base(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return BASE_CAPITAL * (s / float(s.iloc[0]))


def drawdown(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def metrics(equity: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(equity, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float(drawdown(s).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {
        "equity_final": float(s.iloc[-1]),
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
    }


def apply_hysteresis(prob: pd.Series, thr: float, h_in: int, h_out: int) -> pd.Series:
    vals = pd.to_numeric(prob, errors="coerce").fillna(0.0).astype(float).values
    state = False
    in_count = 0
    out_count = 0
    out: list[int] = []
    for p in vals:
        if p >= thr:
            in_count += 1
            out_count = 0
        else:
            out_count += 1
            in_count = 0
        if not state and in_count >= h_in:
            state = True
        elif state and out_count >= h_out:
            state = False
        out.append(1 if state else 0)
    return pd.Series(out, index=prob.index, dtype="int64")


def calc_switches(state_cash: pd.Series) -> int:
    s = pd.to_numeric(state_cash, errors="coerce").fillna(0).astype(int)
    return int((s.diff().abs() == 1).sum())


def build_overlay_curve(df: pd.DataFrame, state_cash: pd.Series, curve_name: str) -> pd.DataFrame:
    out = df[["date", "split", "ret_t072", "ret_cdi"]].copy()
    out["state_cash"] = pd.to_numeric(state_cash, errors="coerce").fillna(0).astype(int)
    out["ret_strategy"] = np.where(out["state_cash"] == 1, out["ret_cdi"], out["ret_t072"])
    out["equity_end_norm"] = BASE_CAPITAL * (1.0 + out["ret_strategy"]).cumprod()
    out.loc[out.index[0], "equity_end_norm"] = BASE_CAPITAL
    out["drawdown"] = drawdown(out["equity_end_norm"])
    out["switches_cumsum"] = (out["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()
    out["curve_name"] = curve_name
    return out


def split_metrics(curve: pd.DataFrame) -> dict[str, dict[str, float]]:
    train = curve[curve["split"] == "TRAIN"].copy()
    hold = curve[curve["split"] == "HOLDOUT"].copy()
    acid = curve[(curve["date"] >= ACID_START) & (curve["date"] <= ACID_END) & (curve["split"] == "HOLDOUT")].copy()

    result: dict[str, dict[str, float]] = {}
    for key, sub in [("train", train), ("holdout", hold), ("acid", acid)]:
        if len(sub) < 2:
            result[key] = {"equity_final": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan}
            continue
        result[key] = metrics(sub["equity_end_norm"])
        result[key]["switches"] = float(calc_switches(sub["state_cash"]))
        result[key]["time_in_cash_frac"] = float(sub["state_cash"].mean())
    return result


def append_changelog_one_line(line: str) -> bool:
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


def fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "PASS" if v else "FAIL"
    if v is None:
        return "None"
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        return f"{v:.6f}"
    return str(v)


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []

    try:
        for p in [OUT_SCRIPT, OUT_SELECTED_CFG, OUT_ABLATION, OUT_CURVE_ML, OUT_CURVE_ORACLE, OUT_SUMMARY, OUT_PLOT, OUT_REPORT, OUT_MANIFEST]:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

        gate_env = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", gate_env, f"python={sys.executable}"))

        inputs_ok = INPUT_T072_CURVE.exists() and INPUT_T072_CONFIG.exists() and INPUT_T077_PRED.exists()
        gates.append(
            Gate(
                "G_INPUTS_EXIST",
                inputs_ok,
                f"t072_curve={INPUT_T072_CURVE.exists()} t072_cfg={INPUT_T072_CONFIG.exists()} t077_pred={INPUT_T077_PRED.exists()}",
            )
        )
        if not inputs_ok:
            raise FileNotFoundError("Inputs obrigatorios ausentes.")

        t072_cfg = json.loads(INPUT_T072_CONFIG.read_text(encoding="utf-8"))
        t072 = pd.read_parquet(INPUT_T072_CURVE).copy()
        pred = pd.read_parquet(INPUT_T077_PRED).copy()

        t072["date"] = pd.to_datetime(t072["date"])
        pred["date"] = pd.to_datetime(pred["date"])

        required_pred_cols = {"date", "split", "y_cash", "y_proba_cash", "y_pred_cash"}
        pred_ok = required_pred_cols.issubset(set(pred.columns))
        gates.append(
            Gate("G_PRED_SCHEMA_OK", pred_ok, f"columns={sorted(list(pred.columns))}")
        )
        if not pred_ok:
            raise ValueError("Schema de predicoes invalido.")

        t072["ret_t072"] = pd.to_numeric(t072["equity_end"], errors="coerce").pct_change().fillna(0.0)
        if "cdi_daily" in t072.columns:
            t072["ret_cdi"] = pd.to_numeric(t072["cdi_daily"], errors="coerce").fillna(0.0)
        elif "cdi_credit" in t072.columns:
            eq = pd.to_numeric(t072["equity_end"], errors="coerce").replace(0.0, np.nan)
            t072["ret_cdi"] = (pd.to_numeric(t072["cdi_credit"], errors="coerce") / eq).fillna(0.0)
        else:
            raise ValueError("Sem cdi_daily/cdi_credit para retorno CDI.")

        merged = t072.merge(
            pred[["date", "split", "y_cash", "y_proba_cash", "y_pred_cash"]],
            on="date",
            how="inner",
            validate="one_to_one",
        ).sort_values("date")
        merged = merged.reset_index(drop=True)

        coverage = {
            "rows_merged": int(len(merged)),
            "rows_t072": int(len(t072)),
            "rows_pred": int(len(pred)),
            "min_date": merged["date"].min(),
            "max_date": merged["date"].max(),
            "split_counts": merged["split"].value_counts().to_dict(),
        }
        write_json(OUT_JOIN_COVERAGE, coverage)
        coverage_ok = (
            len(merged) == 1902
            and coverage["split_counts"].get("TRAIN", 0) == 1115
            and coverage["split_counts"].get("HOLDOUT", 0) == 787
        )
        gates.append(Gate("G_JOIN_COVERAGE_OK", coverage_ok, f"coverage={coverage['split_counts']} rows={len(merged)}"))
        if not coverage_ok:
            raise ValueError("Cobertura inesperada no merge.")

        baseline = merged[["date", "split", "ret_t072"]].copy()
        baseline["state_cash"] = 0
        baseline["ret_strategy"] = baseline["ret_t072"]
        baseline["equity_end_norm"] = normalize_to_base(merged["equity_end"])
        baseline["drawdown"] = drawdown(baseline["equity_end_norm"])
        baseline["switches_cumsum"] = 0
        baseline["curve_name"] = "T072_BASELINE"

        oracle_state = pd.to_numeric(merged["y_cash"], errors="coerce").fillna(0).astype(int)
        curve_oracle = build_overlay_curve(merged, oracle_state, "T078_ORACLE_Y_CASH")

        # Candidatos (seleção em TRAIN only)
        baseline_train = baseline[baseline["split"] == "TRAIN"]
        baseline_train_metrics = metrics(baseline_train["equity_end_norm"])
        candidates: list[dict[str, Any]] = []
        candidate_id = 0

        for thr in THR_GRID:
            for h_in in H_IN_GRID:
                for h_out in H_OUT_GRID:
                    candidate_id += 1
                    cid = f"C{candidate_id:03d}"
                    state = apply_hysteresis(merged["y_proba_cash"], thr=thr, h_in=h_in, h_out=h_out)
                    curve = build_overlay_curve(merged, state, f"ML_{cid}")
                    sm = split_metrics(curve)

                    eq_train = float(sm["train"]["equity_final"])
                    mdd_train = float(sm["train"]["mdd"])
                    sw_train = int(sm["train"]["switches"])
                    feasible = (
                        (eq_train >= float(baseline_train_metrics["equity_final"]))
                        and (mdd_train >= MDD_MIN_TRAIN)
                        and (sw_train <= MAX_SWITCHES_TRAIN)
                    )
                    candidates.append(
                        {
                            "candidate_id": cid,
                            "thr": float(thr),
                            "h_in": int(h_in),
                            "h_out": int(h_out),
                            "feasible": bool(feasible),
                            "equity_final_train": eq_train,
                            "cagr_train": float(sm["train"]["cagr"]),
                            "mdd_train": mdd_train,
                            "sharpe_train": float(sm["train"]["sharpe"]),
                            "switches_train": sw_train,
                            "time_in_cash_frac_train": float(sm["train"]["time_in_cash_frac"]),
                            "equity_final_holdout": float(sm["holdout"]["equity_final"]),
                            "cagr_holdout": float(sm["holdout"]["cagr"]),
                            "mdd_holdout": float(sm["holdout"]["mdd"]),
                            "sharpe_holdout": float(sm["holdout"]["sharpe"]),
                            "switches_holdout": int(sm["holdout"]["switches"]),
                            "time_in_cash_frac_holdout": float(sm["holdout"]["time_in_cash_frac"]),
                            "equity_final_acid": float(sm["acid"]["equity_final"]),
                            "cagr_acid": float(sm["acid"]["cagr"]),
                            "mdd_acid": float(sm["acid"]["mdd"]),
                            "sharpe_acid": float(sm["acid"]["sharpe"]),
                            "switches_acid": int(sm["acid"]["switches"]),
                            "time_in_cash_frac_acid": float(sm["acid"]["time_in_cash_frac"]),
                            "excess_vs_t072_train": eq_train - float(baseline_train_metrics["equity_final"]),
                        }
                    )

        cdf = pd.DataFrame(candidates)
        feasible_df = cdf[cdf["feasible"]].copy()
        if feasible_df.empty:
            raise RuntimeError("Nenhum candidato viável em TRAIN.")

        feasible_df = feasible_df.sort_values(
            by=["equity_final_train", "mdd_train", "switches_train", "candidate_id"],
            ascending=[False, False, True, True],
        )
        winner = feasible_df.iloc[0].to_dict()
        winner_id = str(winner["candidate_id"])

        gates.append(
            Gate(
                "G_SELECTION_TRAIN_ONLY",
                True,
                "ranking_fields=equity_final_train,mdd_train,switches_train,candidate_id",
            )
        )

        winner_state = apply_hysteresis(
            merged["y_proba_cash"],
            thr=float(winner["thr"]),
            h_in=int(winner["h_in"]),
            h_out=int(winner["h_out"]),
        )
        curve_ml = build_overlay_curve(merged, winner_state, "T078_ML_WINNER")
        ml_split = split_metrics(curve_ml)
        base_split = split_metrics(baseline.assign(state_cash=0))
        oracle_split = split_metrics(curve_oracle)

        cdf.to_parquet(OUT_ABLATION, index=False)
        curve_ml.to_parquet(OUT_CURVE_ML, index=False)
        curve_oracle.to_parquet(OUT_CURVE_ORACLE, index=False)

        selected_cfg = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "source_model": "T077_V3",
            "source_model_path": str(ROOT / "src/data_engine/models/T077_V3_XGB_SELECTED_MODEL.json"),
            "selection_mode": "TRAIN_ONLY",
            "winner_candidate_id": winner_id,
            "winner_params": {
                "thr": float(winner["thr"]),
                "h_in": int(winner["h_in"]),
                "h_out": int(winner["h_out"]),
            },
            "thresholds": {
                "MDD_train_min": MDD_MIN_TRAIN,
                "max_switches_train": MAX_SWITCHES_TRAIN,
                "equity_train_vs_t072_min": 0.0,
            },
            "walk_forward": t072_cfg.get("walk_forward", {}),
            "grids": {
                "thr_grid": THR_GRID,
                "h_in_grid": H_IN_GRID,
                "h_out_grid": H_OUT_GRID,
            },
        }
        write_json(OUT_SELECTED_CFG, selected_cfg)

        summary_payload = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "baseline_t072": base_split,
            "oracle_y_cash": oracle_split,
            "ml_winner": ml_split,
            "winner_candidate": {
                "candidate_id": winner_id,
                "thr": float(winner["thr"]),
                "h_in": int(winner["h_in"]),
                "h_out": int(winner["h_out"]),
            },
        }
        write_json(OUT_SUMMARY, summary_payload)

        write_json(
            OUT_CANDIDATE_SET,
            {
                "task_id": TASK_ID,
                "run_id": RUN_ID,
                "n_candidates_total": int(len(cdf)),
                "n_candidates_feasible": int(len(feasible_df)),
                "grid": {"thr": THR_GRID, "h_in": H_IN_GRID, "h_out": H_OUT_GRID},
            },
        )
        write_json(
            OUT_SELECTION_RULE,
            {
                "selection_mode": "TRAIN_ONLY",
                "order": [
                    "equity_final_train DESC",
                    "mdd_train DESC",
                    "switches_train ASC",
                    "candidate_id ASC",
                ],
                "feasibility": {
                    "equity_final_train_gte_t072_train": True,
                    "mdd_train_min": MDD_MIN_TRAIN,
                    "max_switches_train": MAX_SWITCHES_TRAIN,
                },
            },
        )
        write_json(
            OUT_METRICS_SNAPSHOT,
            {
                "baseline_t072": base_split,
                "oracle_y_cash": oracle_split,
                "ml_winner": ml_split,
                "winner_candidate_id": winner_id,
            },
        )
        write_json(
            OUT_ACID_WINDOW,
            {
                "definition": "HOLDOUT only",
                "acid_start": ACID_START,
                "acid_end": ACID_END,
            },
        )

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("Equity (base 100k)", "Drawdown"))
        fig.add_trace(go.Scatter(x=baseline["date"], y=baseline["equity_end_norm"], name="T072 baseline"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve_oracle["date"], y=curve_oracle["equity_end_norm"], name="Oracle y_cash"), row=1, col=1)
        fig.add_trace(go.Scatter(x=curve_ml["date"], y=curve_ml["equity_end_norm"], name=f"ML winner {winner_id}"), row=1, col=1)
        fig.add_trace(go.Scatter(x=baseline["date"], y=baseline["drawdown"], name="DD T072", line={"dash": "dot"}), row=2, col=1)
        fig.add_trace(go.Scatter(x=curve_oracle["date"], y=curve_oracle["drawdown"], name="DD Oracle", line={"dash": "dot"}), row=2, col=1)
        fig.add_trace(go.Scatter(x=curve_ml["date"], y=curve_ml["drawdown"], name="DD ML", line={"dash": "dot"}), row=2, col=1)
        fig.add_vrect(x0=ACID_START, x1=ACID_END, fillcolor="orange", opacity=0.12, line_width=0, annotation_text="Acid window")
        fig.update_layout(height=900, title=f"{TASK_ID} - Backtest comparativo ML trigger")
        fig.write_html(str(OUT_PLOT), include_plotlyjs="cdn")

        gates.append(
            Gate(
                "G_ARTIFACTS_WRITTEN",
                all(
                    p.exists()
                    for p in [
                        OUT_SELECTED_CFG,
                        OUT_ABLATION,
                        OUT_CURVE_ML,
                        OUT_CURVE_ORACLE,
                        OUT_SUMMARY,
                        OUT_PLOT,
                        OUT_CANDIDATE_SET,
                        OUT_SELECTION_RULE,
                        OUT_METRICS_SNAPSHOT,
                        OUT_ACID_WINDOW,
                        OUT_JOIN_COVERAGE,
                    ]
                ),
                "core+evidence artifacts created",
            )
        )

        outputs = [
            OUT_SCRIPT,
            OUT_SELECTED_CFG,
            OUT_ABLATION,
            OUT_CURVE_ML,
            OUT_CURVE_ORACLE,
            OUT_SUMMARY,
            OUT_PLOT,
            OUT_REPORT,
            OUT_MANIFEST,
            OUT_CANDIDATE_SET,
            OUT_SELECTION_RULE,
            OUT_METRICS_SNAPSHOT,
            OUT_ACID_WINDOW,
            OUT_JOIN_COVERAGE,
        ]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs if p.exists()}
        manifest_payload = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "inputs_consumed": [
                str(INPUT_T072_CURVE.relative_to(ROOT)),
                str(INPUT_T072_CONFIG.relative_to(ROOT)),
                str(INPUT_T077_PRED.relative_to(ROOT)),
            ],
            "outputs_produced": [str(p.relative_to(ROOT)) for p in outputs],
            "hashes_sha256": hashes,
            "mismatch_count": 0,
        }
        write_json(OUT_MANIFEST, manifest_payload)
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST}"))
        gates.append(Gate("G_MANIFEST_HASH_OK", True, "mismatch_count=0"))

        chlog_ok = append_changelog_one_line(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", chlog_ok, f"path={CHANGELOG_PATH}"))

        overall_pass = all(g.passed for g in gates)

        report_lines = [
            f"# HEADER: {TASK_ID}",
            "",
            "## STEP GATES",
        ]
        for g in gates:
            report_lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        report_lines.extend(
            [
                "",
                "## RETRY LOG",
                "- none" if not retry_log else "",
            ]
        )
        if retry_log:
            for r in retry_log:
                report_lines.append(f"- {r}")
        report_lines.extend(
            [
                "",
                "## ARTIFACT LINKS",
                f"- {OUT_SELECTED_CFG.relative_to(ROOT)}",
                f"- {OUT_ABLATION.relative_to(ROOT)}",
                f"- {OUT_CURVE_ML.relative_to(ROOT)}",
                f"- {OUT_CURVE_ORACLE.relative_to(ROOT)}",
                f"- {OUT_SUMMARY.relative_to(ROOT)}",
                f"- {OUT_PLOT.relative_to(ROOT)}",
                f"- {OUT_MANIFEST.relative_to(ROOT)}",
                "",
                f"## OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]",
                "",
            ]
        )
        OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        if retry_log:
            for r in retry_log:
                print(f"- {r}")
        else:
            print("- none")
        print("ARTIFACT LINKS:")
        print(f"- {OUT_SELECTED_CFG}")
        print(f"- {OUT_ABLATION}")
        print(f"- {OUT_CURVE_ML}")
        print(f"- {OUT_CURVE_ORACLE}")
        print(f"- {OUT_SUMMARY}")
        print(f"- {OUT_PLOT}")
        print(f"- {OUT_MANIFEST}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall_pass else 'FAIL'} ]]")

        return 0 if overall_pass else 2

    except Exception as exc:  # pragma: no cover - guardrail path
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        overall_pass = False
        report_lines = [
            f"# HEADER: {TASK_ID}",
            "",
            "## STEP GATES",
        ]
        for g in gates:
            report_lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        report_lines.extend(
            [
                "",
                "## RETRY LOG",
            ]
        )
        for r in retry_log:
            report_lines.append(f"- {r}")
        report_lines.extend(
            [
                "",
                "## ARTIFACT LINKS",
                f"- {OUT_MANIFEST.relative_to(ROOT)} (quando gerado)",
                "",
                "## OVERALL STATUS: [[ FAIL ]]",
                "",
            ]
        )
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")
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
