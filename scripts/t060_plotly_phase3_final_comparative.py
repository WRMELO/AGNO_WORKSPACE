#!/usr/bin/env python3
"""T060 - Plotly comparativo final Phase 3 (T059 vs T044 vs T039 vs T037 + CDI + IBOV)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T060-PHASE3-PLOTLY-FINAL-V1"
BASE_CAPITAL = 100000.0
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T039_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T059_CURVE = ROOT / "src/data_engine/portfolio/T059_PORTFOLIO_CURVE_PARTICIPATION_V2.parquet"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"
INPUT_T039_SUMMARY = ROOT / "src/data_engine/portfolio/T039_BASELINE_SUMMARY.json"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_T059_SUMMARY = ROOT / "src/data_engine/portfolio/T059_BASELINE_SUMMARY_V2.json"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
INPUT_T055_SCRIPT = ROOT / "scripts/t055_plotly_phase2_final_comparative.py"
INPUT_T058_SCRIPT = ROOT / "scripts/t058_plotly_start2023_comparative.py"

OUTPUT_HTML = ROOT / "outputs/plots/T060_STATE3_PHASE3_FINAL_COMPARATIVE.html"
OUTPUT_REPORT = ROOT / "outputs/governanca/T060-PHASE3-PLOTLY-FINAL-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T060-PHASE3-PLOTLY-FINAL-V1_manifest.json"
OUTPUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T060-PHASE3-PLOTLY-FINAL-V1_evidence"
OUTPUT_METRICS_SNAPSHOT = OUTPUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUTPUT_PLOT_INVENTORY = OUTPUT_EVIDENCE_DIR / "plot_inventory.json"
SCRIPT_PATH = ROOT / "scripts/t060_plotly_phase3_final_comparative.py"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-02-28T18:30:01Z | VISUALIZATION: T060-PHASE3-PLOTLY-FINAL-V1 EXEC. "
    "Artefatos: outputs/plots/T060_STATE3_PHASE3_FINAL_COMPARATIVE.html; "
    "outputs/governanca/T060-PHASE3-PLOTLY-FINAL-V1_report.md; "
    "outputs/governanca/T060-PHASE3-PLOTLY-FINAL-V1_manifest.json"
)


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
        val = float(obj)
        return val if np.isfinite(val) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if pd.isna(obj):
        return None
    return obj


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def parse_json_strict(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    return json.loads(txt, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid constant: {x}")))


def normalize_to_base(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return BASE_CAPITAL * (s / float(s.iloc[0]))


def compute_drawdown(equity_norm: pd.Series) -> pd.Series:
    s = pd.to_numeric(equity_norm, errors="coerce").astype(float)
    return s / s.cummax() - 1.0


def find_true_intervals(mask: pd.Series, dates: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start = None
    prev_date = None
    for is_true, dt in zip(mask.tolist(), dates.tolist()):
        if is_true and start is None:
            start = dt
        if not is_true and start is not None:
            intervals.append((start, prev_date if prev_date is not None else dt))
            start = None
        prev_date = dt
    if start is not None and prev_date is not None:
        intervals.append((start, prev_date))
    return intervals


def get_metric(d: dict[str, Any], key: str) -> float | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    return fv if np.isfinite(fv) else None


def participation_metrics(curve: pd.DataFrame) -> dict[str, float]:
    c = curve.copy()
    exposure = pd.to_numeric(c.get("exposure", pd.Series(np.nan, index=c.index)), errors="coerce")
    equity = pd.to_numeric(c.get("equity_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash = pd.to_numeric(c.get("cash_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash_weight = (cash / equity.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    defensivo = c.get("regime_defensivo", pd.Series(False, index=c.index)).fillna(False).astype(bool)
    return {
        "time_in_market_frac": float((exposure > 0).mean()) if len(exposure) else np.nan,
        "avg_exposure": float(exposure.mean()) if len(exposure.dropna()) else np.nan,
        "p50_exposure": float(exposure.median()) if len(exposure.dropna()) else np.nan,
        "avg_cash_weight": float(cash_weight.mean()) if len(cash_weight.dropna()) else np.nan,
        "days_cash_ge_090_frac": float((cash_weight >= 0.90).mean()) if len(cash_weight) else np.nan,
        "days_defensive_frac": float(defensivo.mean()) if len(defensivo) else np.nan,
    }


def update_changelog_one_line() -> bool:
    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
    before_len = len(before.encode("utf-8"))
    with CHANGELOG_PATH.open("a", encoding="utf-8") as f:
        if before and not before.endswith("\n"):
            f.write("\n")
        f.write(TRACEABILITY_LINE + "\n")
    after = CHANGELOG_PATH.read_text(encoding="utf-8")
    return len(after.encode("utf-8")) > before_len and after.endswith(TRACEABILITY_LINE + "\n")


def main() -> int:
    print(f"HEADER: {TASK_ID}")

    required_inputs = [
        INPUT_T037_CURVE,
        INPUT_T039_CURVE,
        INPUT_T044_CURVE,
        INPUT_T059_CURVE,
        INPUT_T037_SUMMARY,
        INPUT_T039_SUMMARY,
        INPUT_T044_SUMMARY,
        INPUT_T059_SUMMARY,
        INPUT_MACRO,
        INPUT_T055_SCRIPT,
        INPUT_T058_SCRIPT,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G_MODEL_ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidencia explicita no chat)")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    t037 = pd.read_parquet(INPUT_T037_CURVE).copy()
    t039 = pd.read_parquet(INPUT_T039_CURVE).copy()
    t044 = pd.read_parquet(INPUT_T044_CURVE).copy()
    t059 = pd.read_parquet(INPUT_T059_CURVE).copy()
    macro = pd.read_parquet(INPUT_MACRO).copy()

    for df in [t037, t039, t044, t059, macro]:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

    common_dates = (
        set(t037["date"].dropna())
        & set(t039["date"].dropna())
        & set(t044["date"].dropna())
        & set(t059["date"].dropna())
        & set(macro["date"].dropna())
    )
    common_dates = sorted(pd.to_datetime(list(common_dates)))
    if len(common_dates) < 30:
        print("STEP GATES:")
        print("- G_MODEL_ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidencia explicita no chat)")
        print("- G0_INPUTS_PRESENT: FAIL (intersecao de datas insuficiente)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    def align_curve(df: pd.DataFrame) -> pd.DataFrame:
        out = df[df["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)
        out["equity_norm"] = normalize_to_base(out["equity_end"])
        return out

    t037a = align_curve(t037)
    t039a = align_curve(t039)
    t044a = align_curve(t044)
    t059a = align_curve(t059)
    macroa = macro[macro["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)

    if "cdi_log_daily" not in macroa.columns or "ibov_close" not in macroa.columns:
        print("STEP GATES:")
        print("- G_MODEL_ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidencia explicita no chat)")
        print("- G0_INPUTS_PRESENT: FAIL (macro sem cdi_log_daily/ibov_close)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    cdi_log = pd.to_numeric(macroa["cdi_log_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    cdi_growth = np.exp(np.cumsum(cdi_log.to_numpy(dtype=float)))
    cdi_rebased = BASE_CAPITAL * (cdi_growth / float(cdi_growth[0]))
    ibov_close = pd.to_numeric(macroa["ibov_close"], errors="coerce").ffill().bfill().astype(float)
    ibov_rebased = normalize_to_base(ibov_close)

    dd37 = compute_drawdown(t037a["equity_norm"])
    dd39 = compute_drawdown(t039a["equity_norm"])
    dd44 = compute_drawdown(t044a["equity_norm"])
    dd59 = compute_drawdown(t059a["equity_norm"])

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=[
            "Equity Normalizada (Base R$100k): T059 vs T044 vs T039 vs T037 + CDI + IBOV",
            "Drawdown Overlay: T059 vs T044 vs T039 vs T037",
        ],
    )

    # Equity traces (6)
    fig.add_trace(go.Scatter(x=t059a["date"], y=t059a["equity_norm"], mode="lines", name="T059 Solution", line=dict(color="#9467bd", width=3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=t044a["equity_norm"], mode="lines", name="T044 Phase2 Winner", line=dict(color="#2ca02c", width=2.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t039a["date"], y=t039a["equity_norm"], mode="lines", name="T039 Baseline", line=dict(color="#1f77b4", dash="dot", width=1.7)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t037a["date"], y=t037a["equity_norm"], mode="lines", name="T037 Meta", line=dict(color="#7f7f7f", dash="dash", width=1.7)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=cdi_rebased, mode="lines", name="CDI Acumulado", line=dict(color="#111111", width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=ibov_rebased, mode="lines", name="Ibovespa ^BVSP", line=dict(color="#aec7e8", width=1.6)), row=1, col=1)

    # Drawdown traces (4)
    fig.add_trace(go.Scatter(x=t059a["date"], y=dd59, mode="lines", name="DD T059", line=dict(color="#9467bd", width=2.0)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=dd44, mode="lines", name="DD T044", line=dict(color="#2ca02c", width=1.8)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t039a["date"], y=dd39, mode="lines", name="DD T039", line=dict(color="#1f77b4", dash="dot", width=1.4)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t037a["date"], y=dd37, mode="lines", name="DD T037", line=dict(color="#7f7f7f", dash="dash", width=1.4)), row=2, col=1)

    # Regime shading for available series
    for df, color in [
        (t059a, "rgba(148, 103, 189, 0.06)"),
        (t044a, "rgba(255, 0, 0, 0.08)"),
        (t039a, "rgba(0, 0, 255, 0.05)"),
    ]:
        regime = pd.to_numeric(df.get("regime_defensivo"), errors="coerce").fillna(0).astype(bool)
        for x0, x1 in find_true_intervals(regime, df["date"]):
            fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=1, col=1)
            fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=2, col=1)

    fig.update_layout(
        title="STATE 3 Phase 3 — Comparative Final (T059 vs T044 vs T039 vs T037)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=900,
    )
    fig.update_yaxes(title_text="Patrimonio (R$)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
    fig.update_xaxes(title_text="Data", row=2, col=1)
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn", full_html=True)

    s037 = parse_json_strict(INPUT_T037_SUMMARY)
    s039 = parse_json_strict(INPUT_T039_SUMMARY)
    s044 = parse_json_strict(INPUT_T044_SUMMARY)
    s059 = parse_json_strict(INPUT_T059_SUMMARY)
    m037 = s037
    m039 = s039
    m044 = s044.get("metrics_total", {})
    m059 = s059.get("metrics_total", {})

    pm037 = participation_metrics(t037a)
    pm039 = participation_metrics(t039a)
    pm044 = participation_metrics(t044a)
    pm059 = participation_metrics(t059a)

    metrics_snapshot = {
        "task_id": TASK_ID,
        "date_range": {"start": str(common_dates[0].date()), "end": str(common_dates[-1].date()), "n_dates": len(common_dates)},
        "final_equity_norm": {
            "T059": float(t059a["equity_norm"].iloc[-1]),
            "T044": float(t044a["equity_norm"].iloc[-1]),
            "T039": float(t039a["equity_norm"].iloc[-1]),
            "T037": float(t037a["equity_norm"].iloc[-1]),
            "CDI": float(cdi_rebased[-1]),
            "IBOV": float(ibov_rebased.iloc[-1]),
        },
        "metrics": {
            "T059": {
                "equity_final": get_metric(m059, "equity_final"),
                "CAGR": get_metric(m059, "CAGR"),
                "MDD": get_metric(m059, "MDD"),
                "sharpe": get_metric(m059, "sharpe"),
                "turnover_total": get_metric(m059, "turnover_total"),
                "cost_total": get_metric(m059, "cost_total"),
                "num_switches": get_metric(m059, "num_switches"),
                **pm059,
            },
            "T044": {
                "equity_final": get_metric(m044, "equity_final"),
                "CAGR": get_metric(m044, "CAGR"),
                "MDD": get_metric(m044, "MDD"),
                "sharpe": get_metric(m044, "sharpe"),
                "turnover_total": get_metric(m044, "turnover_total"),
                "cost_total": get_metric(m044, "cost_total"),
                "num_switches": get_metric(m044, "num_switches"),
                **pm044,
            },
            "T039": {
                "equity_final": get_metric(m039, "equity_final"),
                "CAGR": get_metric(m039, "cagr"),
                "MDD": get_metric(m039, "mdd"),
                "sharpe": get_metric(m039, "sharpe"),
                "turnover_total": get_metric(m039, "turnover_total"),
                "cost_total": get_metric(m039, "cost_total"),
                "num_switches": get_metric(m039, "num_switches"),
                **pm039,
            },
            "T037": {
                "equity_final": get_metric(m037, "equity_final"),
                "CAGR": get_metric(m037, "cagr"),
                "MDD": get_metric(m037, "mdd"),
                "sharpe": get_metric(m037, "sharpe"),
                "turnover_total": get_metric(m037, "turnover_total"),
                "cost_total": get_metric(m037, "cost_total"),
                "num_switches": get_metric(m037, "num_switches"),
                **pm037,
            },
        },
    }
    write_json_strict(OUTPUT_METRICS_SNAPSHOT, metrics_snapshot)

    plot_inventory = {
        "task_id": TASK_ID,
        "output_html": str(OUTPUT_HTML),
        "expected_equity_traces": 6,
        "expected_drawdown_traces": 4,
        "total_traces": len(fig.data),
        "trace_names": [trace.name for trace in fig.data],
    }
    write_json_strict(OUTPUT_PLOT_INVENTORY, plot_inventory)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Recorte e inputs",
        f"- date_start: **{common_dates[0].date()}**",
        f"- date_end: **{common_dates[-1].date()}**",
        f"- n_dates_common: **{len(common_dates)}**",
        f"- inputs: `{INPUT_T037_CURVE}`, `{INPUT_T039_CURVE}`, `{INPUT_T044_CURVE}`, `{INPUT_T059_CURVE}`, `{INPUT_MACRO}`",
        "",
        "## 2) Equity final rebased (base R$100k)",
        f"- T059: {metrics_snapshot['final_equity_norm']['T059']:.2f}",
        f"- T044: {metrics_snapshot['final_equity_norm']['T044']:.2f}",
        f"- T039: {metrics_snapshot['final_equity_norm']['T039']:.2f}",
        f"- T037: {metrics_snapshot['final_equity_norm']['T037']:.2f}",
        f"- CDI : {metrics_snapshot['final_equity_norm']['CDI']:.2f}",
        f"- IBOV: {metrics_snapshot['final_equity_norm']['IBOV']:.2f}",
        "",
        "## 3) Risco/retorno (resumo)",
        f"- T059 CAGR={metrics_snapshot['metrics']['T059']['CAGR']}, MDD={metrics_snapshot['metrics']['T059']['MDD']}, Sharpe={metrics_snapshot['metrics']['T059']['sharpe']}",
        f"- T044 CAGR={metrics_snapshot['metrics']['T044']['CAGR']}, MDD={metrics_snapshot['metrics']['T044']['MDD']}, Sharpe={metrics_snapshot['metrics']['T044']['sharpe']}",
        f"- T039 CAGR={metrics_snapshot['metrics']['T039']['CAGR']}, MDD={metrics_snapshot['metrics']['T039']['MDD']}, Sharpe={metrics_snapshot['metrics']['T039']['sharpe']}",
        f"- T037 CAGR={metrics_snapshot['metrics']['T037']['CAGR']}, MDD={metrics_snapshot['metrics']['T037']['MDD']}, Sharpe={metrics_snapshot['metrics']['T037']['sharpe']}",
        "",
        "## 4) Participacao (foco Phase 3)",
        f"- T059 time_in_market={metrics_snapshot['metrics']['T059']['time_in_market_frac']}, avg_exposure={metrics_snapshot['metrics']['T059']['avg_exposure']}, days_cash_ge_090={metrics_snapshot['metrics']['T059']['days_cash_ge_090_frac']}",
        f"- T044 time_in_market={metrics_snapshot['metrics']['T044']['time_in_market_frac']}, avg_exposure={metrics_snapshot['metrics']['T044']['avg_exposure']}, days_cash_ge_090={metrics_snapshot['metrics']['T044']['days_cash_ge_090_frac']}",
        f"- Delta (T059-T044): time_in_market={metrics_snapshot['metrics']['T059']['time_in_market_frac'] - metrics_snapshot['metrics']['T044']['time_in_market_frac']:.4f}, avg_exposure={metrics_snapshot['metrics']['T059']['avg_exposure'] - metrics_snapshot['metrics']['T044']['avg_exposure']:.4f}, days_cash_ge_090={metrics_snapshot['metrics']['T059']['days_cash_ge_090_frac'] - metrics_snapshot['metrics']['T044']['days_cash_ge_090_frac']:.4f}",
        "",
        "## 5) Artefatos",
        f"- `{OUTPUT_HTML}`",
        f"- `{OUTPUT_REPORT}`",
        f"- `{OUTPUT_METRICS_SNAPSHOT}`",
        f"- `{OUTPUT_PLOT_INVENTORY}`",
        f"- `{OUTPUT_MANIFEST}`",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs_for_hash = [OUTPUT_HTML, OUTPUT_REPORT, OUTPUT_METRICS_SNAPSHOT, OUTPUT_PLOT_INVENTORY]
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(p) for p in outputs_for_hash] + [str(OUTPUT_MANIFEST)],
        "hashes_sha256": {str(p): sha256_file(p) for p in (required_inputs + outputs_for_hash)},
    }
    write_json_strict(OUTPUT_MANIFEST, manifest)

    g0 = all(p.exists() for p in required_inputs)
    g1 = OUTPUT_HTML.exists()
    g2 = OUTPUT_METRICS_SNAPSHOT.exists() and OUTPUT_PLOT_INVENTORY.exists() and OUTPUT_REPORT.exists()
    g3 = len(fig.data) == 10
    gch = update_changelog_one_line()
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
    print("- G_MODEL_ROUTING: PASS_MODEL_ROUTING_UNVERIFIED (sem evidencia explicita no chat)")
    print(f"- G0_INPUTS_PRESENT: {'PASS' if g0 else 'FAIL'}")
    print(f"- G1_PLOTLY_PRESENT: {'PASS' if g1 else 'FAIL'}")
    print(f"- G2_EVIDENCE_PRESENT: {'PASS' if g2 else 'FAIL'}")
    print(f"- G3_TRACE_SIGNATURE: {'PASS' if g3 else 'FAIL'} (total_traces={len(fig.data)})")
    print(f"- G_CHLOG_UPDATED: {'PASS' if gch else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("ARTIFACT LINKS:")
    print(f"- {SCRIPT_PATH}")
    print(f"- {OUTPUT_HTML}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUTPUT_METRICS_SNAPSHOT}")
    print(f"- {OUTPUT_PLOT_INVENTORY}")
    print(f"- {OUTPUT_MANIFEST}")
    print(f"- {CHANGELOG_PATH}")

    overall = g0 and g1 and g2 and g3 and gch and gx
    print(f"OVERALL STATUS: [[ {'PASS' if overall else 'FAIL'} ]]")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())

