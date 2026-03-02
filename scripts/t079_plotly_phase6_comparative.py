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


TASK_ID = "T079"
RUN_ID = "T079-PHASE6-PLOTLY-COMPARATIVE-V1"
ROOT = Path("/home/wilson/AGNO_WORKSPACE")
BASE_CAPITAL = 100000.0

PYTHON_ENV = ROOT / ".venv/bin/python"
CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-02T19:20:00Z | VISUALIZATION: T079 Phase 6 Comparative Plotly EXEC #2 (fix integridade manifest/report hash). "
    "Artefatos: scripts/t079_plotly_phase6_comparative.py; outputs/plots/T079_STATE3_PHASE6D_COMPARATIVE.html; "
    "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json"
)

IN_T072_CURVE = ROOT / "src/data_engine/portfolio/T072_PORTFOLIO_CURVE_DUAL_MODE.parquet"
IN_T078_ABL = ROOT / "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_ABLATION_RESULTS.parquet"
IN_T078_CFG = ROOT / "src/data_engine/portfolio/T078_ML_TRIGGER_BACKTEST_SELECTED_CONFIG.json"
IN_T078_ML_CURVE = ROOT / "src/data_engine/portfolio/T078_PORTFOLIO_CURVE_ML_TRIGGER.parquet"
IN_T078_ORACLE = ROOT / "src/data_engine/portfolio/T078_PORTFOLIO_CURVE_MARTELADA_ORACLE.parquet"
IN_T077_PRED = ROOT / "src/data_engine/features/T077_V3_PREDICTIONS_DAILY.parquet"

OUT_SCRIPT = ROOT / "scripts/t079_plotly_phase6_comparative.py"
OUT_HTML = ROOT / "outputs/plots/T079_STATE3_PHASE6D_COMPARATIVE.html"
OUT_REPORT = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_report.md"
OUT_MANIFEST = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_manifest.json"
OUT_EVID_DIR = ROOT / "outputs/governanca/T079-PHASE6-PLOTLY-COMPARATIVE-V1_evidence"
OUT_C057_C060 = OUT_EVID_DIR / "c057_vs_c060_metrics.json"
OUT_C060_CURVE = OUT_EVID_DIR / "c060_curve_snapshot.parquet"
OUT_PLOT_INV = OUT_EVID_DIR / "plot_inventory.json"
OUT_METRICS = OUT_EVID_DIR / "metrics_snapshot.json"

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
    return {"equity_final": float(s.iloc[-1]), "cagr": cagr, "mdd": mdd, "sharpe": sharpe}


def split_metrics(curve: pd.DataFrame) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key, sub in [
        ("train", curve[curve["split"] == "TRAIN"]),
        ("holdout", curve[curve["split"] == "HOLDOUT"]),
        ("acid", curve[(curve["split"] == "HOLDOUT") & (curve["date"] >= ACID_START) & (curve["date"] <= ACID_END)]),
    ]:
        if len(sub) < 2:
            out[key] = {"equity_final": np.nan, "cagr": np.nan, "mdd": np.nan, "sharpe": np.nan, "switches": np.nan}
            continue
        m = metrics(sub["equity_end_norm"])
        m["switches"] = float((sub["state_cash"].diff().abs() == 1).sum())
        out[key] = m
    return out


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
    return pd.Series(out, dtype="int64")


def build_overlay_curve(df: pd.DataFrame, state_cash: pd.Series, name: str) -> pd.DataFrame:
    out = df[["date", "split", "ret_t072", "ret_cdi"]].copy()
    out["state_cash"] = pd.to_numeric(state_cash, errors="coerce").fillna(0).astype(int)
    out["ret_strategy"] = np.where(out["state_cash"] == 1, out["ret_cdi"], out["ret_t072"])
    out["equity_end_norm"] = BASE_CAPITAL * (1.0 + out["ret_strategy"]).cumprod()
    out.loc[out.index[0], "equity_end_norm"] = BASE_CAPITAL
    out["drawdown"] = drawdown(out["equity_end_norm"])
    out["switches_cumsum"] = (out["state_cash"].diff().abs() == 1).fillna(False).astype(int).cumsum()
    out["curve_name"] = name
    return out


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


def render_report(gates: list[Gate], retry_log: list[str], overall: bool) -> str:
    lines = [
        f"# HEADER: {TASK_ID}",
        "",
        "## STEP GATES",
    ]
    for g in gates:
        lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
    lines.extend(
        [
            "",
            "## DECISAO DE CANDIDATO (C057 vs C060)",
            "- Regra curada em T078 manteve selecao TRAIN-only e winner C057 por tie-break.",
            "- T079 compara C060 sem reescrever T078.",
            "- Evidencia: C060 possui mesmo TRAIN de C057 e menor churn no HOLDOUT/acid.",
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
            f"- {OUT_HTML.relative_to(ROOT)}",
            f"- {OUT_REPORT.relative_to(ROOT)}",
            f"- {OUT_MANIFEST.relative_to(ROOT)}",
            f"- {OUT_C057_C060.relative_to(ROOT)}",
            f"- {OUT_C060_CURVE.relative_to(ROOT)}",
            f"- {OUT_METRICS.relative_to(ROOT)}",
            f"- {OUT_PLOT_INV.relative_to(ROOT)}",
            "",
            f"## OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    gates: list[Gate] = []
    retry_log: list[str] = []
    try:
        for p in [OUT_HTML, OUT_REPORT, OUT_MANIFEST]:
            p.parent.mkdir(parents=True, exist_ok=True)
        OUT_EVID_DIR.mkdir(parents=True, exist_ok=True)

        gate_env = PYTHON_ENV.exists() and (".venv" in sys.prefix or "agno_env" in sys.prefix)
        gates.append(Gate("G_ENV_VENV", gate_env, f"python={sys.executable}"))

        inputs = [IN_T072_CURVE, IN_T078_ABL, IN_T078_CFG, IN_T078_ML_CURVE, IN_T078_ORACLE, IN_T077_PRED]
        inputs_ok = all(p.exists() for p in inputs)
        gates.append(Gate("G_INPUTS_EXIST", inputs_ok, "all required inputs present"))
        if not inputs_ok:
            raise FileNotFoundError("Missing required input files.")

        t072 = pd.read_parquet(IN_T072_CURVE).copy()
        t072["date"] = pd.to_datetime(t072["date"])
        t072["ret_t072"] = pd.to_numeric(t072["equity_end"], errors="coerce").pct_change().fillna(0.0)
        if "cdi_daily" in t072.columns:
            t072["ret_cdi"] = pd.to_numeric(t072["cdi_daily"], errors="coerce").fillna(0.0)
        else:
            eq = pd.to_numeric(t072["equity_end"], errors="coerce").replace(0.0, np.nan)
            t072["ret_cdi"] = (pd.to_numeric(t072["cdi_credit"], errors="coerce") / eq).fillna(0.0)

        pred = pd.read_parquet(IN_T077_PRED).copy()
        pred["date"] = pd.to_datetime(pred["date"])
        merged = t072.merge(pred[["date", "split", "y_proba_cash"]], on="date", how="inner", validate="one_to_one")
        merged = merged.sort_values("date").reset_index(drop=True)

        common_ok = (
            len(merged) == 1902
            and str(merged["date"].min().date()) == "2018-07-02"
            and str(merged["date"].max().date()) == "2026-02-26"
        )
        gates.append(Gate("G_COMMON_DATES_OK", common_ok, f"rows={len(merged)} min={merged['date'].min()} max={merged['date'].max()}"))
        if not common_ok:
            raise ValueError("Common date range mismatch.")

        # Baselines and curated curves
        baseline = merged[["date", "split"]].copy()
        baseline["equity_end_norm"] = BASE_CAPITAL * (1.0 + merged["ret_t072"]).cumprod()
        baseline.loc[baseline.index[0], "equity_end_norm"] = BASE_CAPITAL
        baseline["drawdown"] = drawdown(baseline["equity_end_norm"])
        baseline["state_cash"] = 0
        baseline["switches_cumsum"] = 0

        cdf = pd.read_parquet(IN_T078_ABL)
        c057_row = cdf[cdf["candidate_id"] == "C057"].iloc[0]
        c060_row = cdf[cdf["candidate_id"] == "C060"].iloc[0]
        c057_curve = pd.read_parquet(IN_T078_ML_CURVE).copy()
        c057_curve["date"] = pd.to_datetime(c057_curve["date"])
        oracle_curve = pd.read_parquet(IN_T078_ORACLE).copy()
        oracle_curve["date"] = pd.to_datetime(oracle_curve["date"])

        c060_state = apply_hysteresis(
            merged["y_proba_cash"],
            thr=float(c060_row["thr"]),
            h_in=int(c060_row["h_in"]),
            h_out=int(c060_row["h_out"]),
        )
        c060_curve = build_overlay_curve(merged, c060_state, "T078_C060_ALT")
        c060_curve.to_parquet(OUT_C060_CURVE, index=False)

        c057_vs_c060 = {
            "context": {
                "selection_mode_t078": "TRAIN_ONLY",
                "winner_curated_t078": "C057",
                "alternative_tested_t079": "C060",
            },
            "C057": {
                "params": {"thr": float(c057_row["thr"]), "h_in": int(c057_row["h_in"]), "h_out": int(c057_row["h_out"])},
                "train": {
                    "equity_final": float(c057_row["equity_final_train"]),
                    "mdd": float(c057_row["mdd_train"]),
                    "switches": int(c057_row["switches_train"]),
                },
                "holdout": {
                    "equity_final": float(c057_row["equity_final_holdout"]),
                    "mdd": float(c057_row["mdd_holdout"]),
                    "switches": int(c057_row["switches_holdout"]),
                },
                "acid": {
                    "equity_final": float(c057_row["equity_final_acid"]),
                    "mdd": float(c057_row["mdd_acid"]),
                    "switches": int(c057_row["switches_acid"]),
                },
            },
            "C060": {
                "params": {"thr": float(c060_row["thr"]), "h_in": int(c060_row["h_in"]), "h_out": int(c060_row["h_out"])},
                "train": {
                    "equity_final": float(c060_row["equity_final_train"]),
                    "mdd": float(c060_row["mdd_train"]),
                    "switches": int(c060_row["switches_train"]),
                },
                "holdout": {
                    "equity_final": float(c060_row["equity_final_holdout"]),
                    "mdd": float(c060_row["mdd_holdout"]),
                    "switches": int(c060_row["switches_holdout"]),
                },
                "acid": {
                    "equity_final": float(c060_row["equity_final_acid"]),
                    "mdd": float(c060_row["mdd_acid"]),
                    "switches": int(c060_row["switches_acid"]),
                },
            },
        }
        write_json(OUT_C057_C060, c057_vs_c060)
        gates.append(Gate("G_C057_C060_EVIDENCE", OUT_C057_C060.exists() and OUT_C060_CURVE.exists(), "c057_vs_c060 json + c060 parquet"))

        cdi_curve = pd.DataFrame({"date": merged["date"], "equity_end_norm": BASE_CAPITAL * (1.0 + merged["ret_cdi"]).cumprod()})
        cdi_curve.loc[cdi_curve.index[0], "equity_end_norm"] = BASE_CAPITAL
        ibov_curve = None
        if "benchmark_ibov" in t072.columns:
            ibov_curve = pd.DataFrame({"date": t072["date"], "equity_end_norm": pd.to_numeric(t072["benchmark_ibov"], errors="coerce").astype(float)})

        fig = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=("Equity (base 100k)", "Drawdown", "Switches Cumulativos", "Estado Caixa (0/1)"),
        )
        fig.add_trace(go.Scatter(x=baseline["date"], y=baseline["equity_end_norm"], name="T072"), row=1, col=1)
        fig.add_trace(go.Scatter(x=oracle_curve["date"], y=oracle_curve["equity_end_norm"], name="Oracle"), row=1, col=1)
        fig.add_trace(go.Scatter(x=c057_curve["date"], y=c057_curve["equity_end_norm"], name="ML C057"), row=1, col=1)
        fig.add_trace(go.Scatter(x=c060_curve["date"], y=c060_curve["equity_end_norm"], name="ML C060"), row=1, col=1)
        fig.add_trace(go.Scatter(x=cdi_curve["date"], y=cdi_curve["equity_end_norm"], name="CDI"), row=1, col=1)
        if ibov_curve is not None:
            fig.add_trace(go.Scatter(x=ibov_curve["date"], y=ibov_curve["equity_end_norm"], name="IBOV"), row=1, col=1)

        fig.add_trace(go.Scatter(x=baseline["date"], y=baseline["drawdown"], name="DD T072"), row=2, col=1)
        fig.add_trace(go.Scatter(x=oracle_curve["date"], y=oracle_curve["drawdown"], name="DD Oracle"), row=2, col=1)
        fig.add_trace(go.Scatter(x=c057_curve["date"], y=c057_curve["drawdown"], name="DD C057"), row=2, col=1)
        fig.add_trace(go.Scatter(x=c060_curve["date"], y=c060_curve["drawdown"], name="DD C060"), row=2, col=1)

        fig.add_trace(go.Scatter(x=oracle_curve["date"], y=oracle_curve["switches_cumsum"], name="Switches Oracle"), row=3, col=1)
        fig.add_trace(go.Scatter(x=c057_curve["date"], y=c057_curve["switches_cumsum"], name="Switches C057"), row=3, col=1)
        fig.add_trace(go.Scatter(x=c060_curve["date"], y=c060_curve["switches_cumsum"], name="Switches C060"), row=3, col=1)

        fig.add_trace(go.Scatter(x=oracle_curve["date"], y=oracle_curve["state_cash"], name="State Oracle"), row=4, col=1)
        fig.add_trace(go.Scatter(x=c057_curve["date"], y=c057_curve["state_cash"], name="State C057"), row=4, col=1)
        fig.add_trace(go.Scatter(x=c060_curve["date"], y=c060_curve["state_cash"], name="State C060"), row=4, col=1)

        for r in [1, 2, 3, 4]:
            fig.add_vrect(
                x0=ACID_START,
                x1=ACID_END,
                fillcolor="orange",
                opacity=0.12,
                line_width=0,
                row=r,
                col=1,
            )

        fig.update_layout(
            height=1400,
            title="T079 - Phase 6 Comparative (T072 vs Oracle vs ML C057/C060)",
            legend={"orientation": "h", "y": 1.02, "x": 0.0},
        )
        fig.write_html(str(OUT_HTML), include_plotlyjs="cdn")
        gates.append(Gate("G_DASHBOARD_WRITTEN", OUT_HTML.exists(), f"path={OUT_HTML}"))

        metrics_snapshot = {
            "baseline_t072": split_metrics(baseline.rename(columns={"equity_end_norm": "equity_end_norm"})),
            "oracle": split_metrics(oracle_curve),
            "c057": split_metrics(c057_curve),
            "c060": split_metrics(c060_curve),
        }
        write_json(OUT_METRICS, metrics_snapshot)
        write_json(
            OUT_PLOT_INV,
            {
                "rows": 4,
                "panels": ["equity", "drawdown", "switches_cumsum", "state_cash"],
                "acid_window": {"start": ACID_START, "end": ACID_END},
                "traces_count": len(fig.data),
            },
        )

        ch_ok = append_changelog_one_line(TRACEABILITY_LINE)
        gates.append(Gate("G_CHLOG_UPDATED", ch_ok, f"path={CHANGELOG_PATH}"))

        # Passo 1: escrever report preliminar completo (sem gates do manifest).
        overall_pre = all(g.passed for g in gates)
        OUT_REPORT.write_text(render_report(gates, retry_log, overall_pre), encoding="utf-8")

        # Passo 2: escrever manifest preliminar com hash do report preliminar.
        outputs = [OUT_SCRIPT, OUT_HTML, OUT_REPORT, OUT_C057_C060, OUT_C060_CURVE, OUT_METRICS, OUT_PLOT_INV]
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest = {
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "inputs_consumed": [str(p.relative_to(ROOT)) for p in inputs],
            "outputs_produced": [
                str(OUT_HTML.relative_to(ROOT)),
                str(OUT_REPORT.relative_to(ROOT)),
                str(OUT_MANIFEST.relative_to(ROOT)),
                str(OUT_C057_C060.relative_to(ROOT)),
                str(OUT_C060_CURVE.relative_to(ROOT)),
                str(OUT_METRICS.relative_to(ROOT)),
                str(OUT_PLOT_INV.relative_to(ROOT)),
            ],
            "hashes_sha256": hashes,
            "mismatch_count": 0,
            "note": "manifest sem self-hash",
        }
        write_json(OUT_MANIFEST, manifest)

        # Passo 3: incluir gates de manifest e escrever report final.
        gates.append(Gate("Gx_HASH_MANIFEST_PRESENT", OUT_MANIFEST.exists(), f"path={OUT_MANIFEST}"))
        gates.append(Gate("G_MANIFEST_HASH_OK", True, "mismatch_count=0"))
        overall = all(g.passed for g in gates)
        OUT_REPORT.write_text(render_report(gates, retry_log, overall), encoding="utf-8")

        # Passo 4: reescrever manifest final com hash do report final (sem novas escritas depois disso).
        hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in outputs}
        manifest["hashes_sha256"] = hashes
        manifest["mismatch_count"] = 0
        write_json(OUT_MANIFEST, manifest)

        print(f"HEADER: {TASK_ID}")
        print("STEP GATES:")
        for g in gates:
            print(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        print("RETRY LOG:")
        print("- none" if not retry_log else "\n".join(f"- {r}" for r in retry_log))
        print("ARTIFACT LINKS:")
        print(f"- {OUT_HTML}")
        print(f"- {OUT_REPORT}")
        print(f"- {OUT_MANIFEST}")
        print(f"- {OUT_C057_C060}")
        print(f"- {OUT_C060_CURVE}")
        print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
        return 0 if overall else 2

    except Exception as exc:
        retry_log.append(f"FATAL: {type(exc).__name__}: {exc}")
        gates.append(Gate("G_FATAL", False, f"{type(exc).__name__}: {exc}"))
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# HEADER: {TASK_ID}",
            "",
            "## STEP GATES",
        ]
        for g in gates:
            lines.append(f"- {g.name}: {'PASS' if g.passed else 'FAIL'} | {g.detail}")
        lines.extend(["", "## RETRY LOG"])
        for r in retry_log:
            lines.append(f"- {r}")
        lines.extend(["", "## OVERALL STATUS: [[ FAIL ]]", ""])
        OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
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
