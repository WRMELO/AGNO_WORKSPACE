#!/usr/bin/env python3
"""T055 - Plotly comparativo final Phase 2 (T044 vs T037 vs T039)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T055-PHASE2-PLOTLY-FINAL-V1"
BASE_CAPITAL = 100000.0
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T039_CURVE = ROOT / "src/data_engine/portfolio/T039_PORTFOLIO_CURVE.parquet"
INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"
INPUT_T039_SUMMARY = ROOT / "src/data_engine/portfolio/T039_BASELINE_SUMMARY.json"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"

OUTPUT_HTML = ROOT / "outputs/plots/T055_STATE3_PHASE2_FINAL_COMPARATIVE.html"
OUTPUT_REPORT = ROOT / "outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_manifest.json"
OUTPUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T055-PHASE2-PLOTLY-FINAL-V1_evidence"
OUTPUT_METRICS_SNAPSHOT = OUTPUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUTPUT_PLOT_INVENTORY = OUTPUT_EVIDENCE_DIR / "plot_inventory.json"
SCRIPT_PATH = ROOT / "scripts/t055_plotly_phase2_final_comparative.py"


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
        if not np.isfinite(val):
            return None
        return val
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def write_json_strict(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = _json_safe(payload)
    path.write_text(json.dumps(safe, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def parse_json_strict(path: Path) -> Any:
    txt = path.read_text(encoding="utf-8")
    return json.loads(txt, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid constant: {x}")))


def normalize_series(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    return BASE_CAPITAL * (s / float(s.iloc[0]))


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


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "N/A"
    return f"{x * 100:.2f}%"


def fmt_num(x: float | None, dec: int = 2) -> str:
    if x is None:
        return "N/A"
    return f"{x:,.{dec}f}"


def get_metric(d: dict[str, Any], key: str) -> float | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(fv):
        return None
    return fv


def build_metrics_table(metrics: dict[str, dict[str, float | None]]) -> str:
    rows = [
        ("equity_final", "brl", "Equity Final"),
        ("cagr", "pct", "CAGR"),
        ("mdd", "pct", "MDD"),
        ("sharpe", "num", "Sharpe"),
        ("turnover_total", "num", "Turnover Total (x)"),
        ("cost_total", "brl", "Custo Total (R$)"),
        ("num_switches", "int", "Num Switches"),
    ]
    html = [
        "<h3 style='margin:10px 0 6px 0;'>Tabela Comparativa de Métricas (Summaries)</h3>",
        "<table style='border-collapse:collapse;width:100%;font-family:Arial,sans-serif;'>",
        "<thead><tr style='background:#f3f3f3;'>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:left;'>Métrica</th>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:right;'>T044 (Solution)</th>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:right;'>T037 (Meta)</th>"
        "<th style='border:1px solid #ddd;padding:8px;text-align:right;'>T039 (Baseline)</th>"
        "</tr></thead><tbody>",
    ]
    for key, kind, label in rows:
        v044 = metrics["T044"].get(key)
        v037 = metrics["T037"].get(key)
        v039 = metrics["T039"].get(key)
        if kind == "pct":
            s044, s037, s039 = fmt_pct(v044), fmt_pct(v037), fmt_pct(v039)
        elif kind == "brl":
            s044 = f"R$ {fmt_num(v044)}"
            s037 = f"R$ {fmt_num(v037)}"
            s039 = f"R$ {fmt_num(v039)}"
        elif kind == "int":
            s044, s037, s039 = fmt_num(v044, 0), fmt_num(v037, 0), fmt_num(v039, 0)
        else:
            s044, s037, s039 = fmt_num(v044), fmt_num(v037), fmt_num(v039)
        html.append(
            "<tr>"
            f"<td style='border:1px solid #ddd;padding:8px;'>{label}</td>"
            f"<td style='border:1px solid #ddd;padding:8px;text-align:right;'>{s044}</td>"
            f"<td style='border:1px solid #ddd;padding:8px;text-align:right;'>{s037}</td>"
            f"<td style='border:1px solid #ddd;padding:8px;text-align:right;'>{s039}</td>"
            "</tr>"
        )
    html.append("</tbody></table>")
    return "".join(html)


def nearest_y(df: pd.DataFrame, target: pd.Timestamp, col: str) -> float:
    idx = (df["date"] - target).abs().idxmin()
    return float(df.loc[idx, col])


def read_metrics() -> dict[str, dict[str, float | None]]:
    t037 = parse_json_strict(INPUT_T037_SUMMARY)
    t039 = parse_json_strict(INPUT_T039_SUMMARY)
    t044 = parse_json_strict(INPUT_T044_SUMMARY)
    m044 = t044.get("metrics_total", {})
    return {
        "T044": {
            "equity_final": get_metric(m044, "equity_final"),
            "cagr": get_metric(m044, "CAGR"),
            "mdd": get_metric(m044, "MDD"),
            "sharpe": get_metric(m044, "sharpe"),
            "turnover_total": get_metric(m044, "turnover_total"),
            "cost_total": get_metric(m044, "cost_total"),
            "num_switches": get_metric(m044, "num_switches"),
        },
        "T037": {
            "equity_final": get_metric(t037, "equity_final"),
            "cagr": get_metric(t037, "cagr"),
            "mdd": get_metric(t037, "mdd"),
            "sharpe": get_metric(t037, "sharpe"),
            "turnover_total": get_metric(t037, "turnover_total"),
            "cost_total": get_metric(t037, "total_cost"),
            "num_switches": get_metric(t037, "num_switches"),
        },
        "T039": {
            "equity_final": get_metric(t039, "equity_final"),
            "cagr": get_metric(t039, "cagr"),
            "mdd": get_metric(t039, "mdd"),
            "sharpe": get_metric(t039, "sharpe"),
            "turnover_total": get_metric(t039, "turnover_total"),
            "cost_total": get_metric(t039, "total_cost"),
            "num_switches": get_metric(t039, "num_switches"),
        },
    }


def beat_high(v: float | None, ref: float | None) -> bool | None:
    if v is None or ref is None:
        return None
    return bool(v > ref)


def beat_mdd(v: float | None, ref: float | None) -> bool | None:
    if v is None or ref is None:
        return None
    return bool(v > ref)


def main() -> int:
    print(f"HEADER: {TASK_ID}")
    print("STEP GATES:")

    required_inputs = [
        INPUT_T037_CURVE,
        INPUT_T039_CURVE,
        INPUT_T044_CURVE,
        INPUT_T037_SUMMARY,
        INPUT_T039_SUMMARY,
        INPUT_T044_SUMMARY,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    g1 = len(missing) == 0
    print(f"- G1_INPUTS_PRESENT: {'PASS' if g1 else 'FAIL'}")
    if not g1:
        print(f"  missing={missing}")
        print("RETRY LOG: NONE")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    t037 = pd.read_parquet(INPUT_T037_CURVE).copy()
    t039 = pd.read_parquet(INPUT_T039_CURVE).copy()
    t044 = pd.read_parquet(INPUT_T044_CURVE).copy()

    for df in [t037, t039, t044]:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df.sort_values("date", inplace=True)
        df.drop_duplicates(subset=["date"], keep="last", inplace=True)
        df.reset_index(drop=True, inplace=True)

    common_dates = sorted(set(t037["date"]).intersection(set(t039["date"])).intersection(set(t044["date"])))
    g2 = len(common_dates) > 0
    print(f"- G2_COMMON_DATES_NONEMPTY: {'PASS' if g2 else 'FAIL'}")
    if not g2:
        print("RETRY LOG: NONE")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    t037a = t037[t037["date"].isin(common_dates)].copy().reset_index(drop=True)
    t039a = t039[t039["date"].isin(common_dates)].copy().reset_index(drop=True)
    t044a = t044[t044["date"].isin(common_dates)].copy().reset_index(drop=True)

    t037a["equity_norm"] = normalize_series(t037a["equity_end"])
    t039a["equity_norm"] = normalize_series(t039a["equity_end"])
    t044a["equity_norm"] = normalize_series(t044a["equity_end"])

    cdi_daily = pd.to_numeric(t044a["cdi_daily"], errors="coerce").fillna(0.0).astype(float)
    cdi_equity = BASE_CAPITAL * (1.0 + cdi_daily).cumprod()
    cdi_equity = BASE_CAPITAL * (cdi_equity / float(cdi_equity.iloc[0]))

    ibov = pd.to_numeric(t044a["ibov_close"], errors="coerce").ffill().bfill().astype(float)
    ibov_equity = BASE_CAPITAL * (ibov / float(ibov.iloc[0]))

    dd37 = t037a["equity_norm"] / t037a["equity_norm"].cummax() - 1.0
    dd39 = t039a["equity_norm"] / t039a["equity_norm"].cummax() - 1.0
    dd44 = t044a["equity_norm"] / t044a["equity_norm"].cummax() - 1.0

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=[
            "Equity Normalizada (Base R$100k): T044 vs T037 vs T039 + CDI + IBOV",
            "Drawdown Overlay: T044 vs T037 vs T039",
        ],
    )

    fig.add_trace(
        go.Scatter(x=t044a["date"], y=t044a["equity_norm"], mode="lines", name="T044 Solution", line=dict(color="#2ca02c", width=3)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=t037a["date"],
            y=t037a["equity_norm"],
            mode="lines",
            name="T037 Meta",
            line=dict(color="#7f7f7f", dash="dash", width=1.7),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=t039a["date"],
            y=t039a["equity_norm"],
            mode="lines",
            name="T039 Baseline",
            line=dict(color="#1f77b4", dash="dot", width=1.7),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=t044a["date"], y=cdi_equity, mode="lines", name="CDI Acumulado", line=dict(color="#bdbdbd", dash="dash", width=1.3)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=t044a["date"], y=ibov_equity, mode="lines", name="Ibovespa ^BVSP", line=dict(color="#ff7f0e", dash="dot", width=1.3)),
        row=1,
        col=1,
    )

    fig.add_trace(go.Scatter(x=t044a["date"], y=dd44, mode="lines", name="DD T044", line=dict(color="#2ca02c", width=2.2)), row=2, col=1)
    fig.add_trace(
        go.Scatter(x=t037a["date"], y=dd37, mode="lines", name="DD T037", line=dict(color="#7f7f7f", dash="dash", width=1.4)),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=t039a["date"], y=dd39, mode="lines", name="DD T039", line=dict(color="#1f77b4", dash="dot", width=1.4)),
        row=2,
        col=1,
    )

    regime44 = pd.to_numeric(t044a.get("regime_defensivo"), errors="coerce").fillna(0).astype(bool)
    regime39 = pd.to_numeric(t039a.get("regime_defensivo"), errors="coerce").fillna(0).astype(bool)
    for x0, x1 in find_true_intervals(regime44, t044a["date"]):
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(255, 0, 0, 0.08)", line_width=0, layer="below", row=1, col=1)
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(255, 0, 0, 0.08)", line_width=0, layer="below", row=2, col=1)
    for x0, x1 in find_true_intervals(regime39, t039a["date"]):
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(0, 0, 255, 0.05)", line_width=0, layer="below", row=1, col=1)
        fig.add_vrect(x0=x0, x1=x1, fillcolor="rgba(0, 0, 255, 0.05)", line_width=0, layer="below", row=2, col=1)

    covid = pd.Timestamp("2020-03-23")
    selic = pd.Timestamp("2021-03-17")
    fig.add_annotation(x=covid, y=nearest_y(t044a, covid, "equity_norm"), text="COVID Crash", showarrow=True, arrowhead=1, ay=-35, row=1, col=1)
    fig.add_annotation(
        x=selic,
        y=nearest_y(t044a, selic, "equity_norm"),
        text="Início Alta Selic",
        showarrow=True,
        arrowhead=1,
        ay=-35,
        row=1,
        col=1,
    )

    fig.update_layout(
        title="STATE 3 Phase 2 — Comparativo Final (T044 vs T037 vs T039)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=900,
    )
    fig.update_yaxes(title_text="Patrimônio (R$)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
    fig.update_xaxes(title_text="Data", row=2, col=1)

    g3 = len(fig.data) == 8
    print(f"- G3_PLOT_BUILT: {'PASS' if g3 else 'FAIL'} (traces={len(fig.data)})")

    metrics = read_metrics()
    beats = {
        "equity_final": {
            "vs_t037": beat_high(metrics["T044"]["equity_final"], metrics["T037"]["equity_final"]),
            "vs_t039": beat_high(metrics["T044"]["equity_final"], metrics["T039"]["equity_final"]),
        },
        "cagr": {
            "vs_t037": beat_high(metrics["T044"]["cagr"], metrics["T037"]["cagr"]),
            "vs_t039": beat_high(metrics["T044"]["cagr"], metrics["T039"]["cagr"]),
        },
        "mdd": {
            "vs_t037": beat_mdd(metrics["T044"]["mdd"], metrics["T037"]["mdd"]),
            "vs_t039": beat_mdd(metrics["T044"]["mdd"], metrics["T039"]["mdd"]),
        },
        "sharpe": {
            "vs_t037": beat_high(metrics["T044"]["sharpe"], metrics["T037"]["sharpe"]),
            "vs_t039": beat_high(metrics["T044"]["sharpe"], metrics["T039"]["sharpe"]),
        },
    }

    table_html = build_metrics_table(metrics)
    plot_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    final_html = (
        "<html><head><meta charset='utf-8'><title>T055 STATE3 Phase2 Final</title></head>"
        "<body style='max-width:1500px;margin:0 auto;padding:10px;'>"
        f"{plot_html}"
        f"{table_html}"
        "<p style='font-size:12px;color:#666;'>"
        "Shading vermelho: regime defensivo T044. Shading azul: regime defensivo T039."
        "</p>"
        "</body></html>"
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(final_html, encoding="utf-8")

    metrics_snapshot = {
        "task_id": TASK_ID,
        "date_range": {
            "min": str(pd.to_datetime(t044a["date"].min()).date()),
            "max": str(pd.to_datetime(t044a["date"].max()).date()),
            "n_dates": int(len(t044a)),
        },
        "final_equity_norm": {
            "T044": float(t044a["equity_norm"].iloc[-1]),
            "T037": float(t037a["equity_norm"].iloc[-1]),
            "T039": float(t039a["equity_norm"].iloc[-1]),
            "CDI": float(cdi_equity.iloc[-1]),
            "IBOV": float(ibov_equity.iloc[-1]),
        },
        "metrics_from_summaries": metrics,
        "beats_check": beats,
    }
    plot_inventory = {
        "task_id": TASK_ID,
        "subplot_count": 2,
        "trace_count": int(len(fig.data)),
        "trace_names": [str(tr.name) for tr in fig.data],
        "equity_traces_expected": ["T044 Solution", "T037 Meta", "T039 Baseline", "CDI Acumulado", "Ibovespa ^BVSP"],
        "drawdown_traces_expected": ["DD T044", "DD T037", "DD T039"],
    }

    write_json_strict(OUTPUT_METRICS_SNAPSHOT, metrics_snapshot)
    write_json_strict(OUTPUT_PLOT_INVENTORY, plot_inventory)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Scope",
        "- Plotly comparativo final Phase 2 com T044 (solution), T037 (meta), T039 (baseline), CDI e IBOV.",
        "",
        "## 2) Gates",
        f"- G1_INPUTS_PRESENT: {'PASS' if g1 else 'FAIL'}",
        f"- G2_COMMON_DATES_NONEMPTY: {'PASS' if g2 else 'FAIL'}",
        f"- G3_PLOT_BUILT: {'PASS' if g3 else 'FAIL'}",
        "- G4_WRITE_ARTIFACTS: PENDING",
        "- G5_STRICT_JSON: PENDING",
        "- G6_MANIFEST_SELF_HASH_EXCLUDED: PENDING",
        "- Gx_HASH_MANIFEST_PRESENT: PENDING",
        "",
        "## 3) Final equity normalized (base 100k)",
        f"- T044: {metrics_snapshot['final_equity_norm']['T044']:.2f}",
        f"- T037: {metrics_snapshot['final_equity_norm']['T037']:.2f}",
        f"- T039: {metrics_snapshot['final_equity_norm']['T039']:.2f}",
        f"- CDI : {metrics_snapshot['final_equity_norm']['CDI']:.2f}",
        f"- IBOV: {metrics_snapshot['final_equity_norm']['IBOV']:.2f}",
        "",
        "## 4) Beats check (T044 vs T037/T039)",
        f"- equity_final: vs T037={beats['equity_final']['vs_t037']} | vs T039={beats['equity_final']['vs_t039']}",
        f"- CAGR: vs T037={beats['cagr']['vs_t037']} | vs T039={beats['cagr']['vs_t039']}",
        f"- MDD: vs T037={beats['mdd']['vs_t037']} | vs T039={beats['mdd']['vs_t039']}",
        f"- Sharpe: vs T037={beats['sharpe']['vs_t037']} | vs T039={beats['sharpe']['vs_t039']}",
        "",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

    outputs = [
        OUTPUT_HTML,
        OUTPUT_REPORT,
        OUTPUT_MANIFEST,
        OUTPUT_METRICS_SNAPSHOT,
        OUTPUT_PLOT_INVENTORY,
        SCRIPT_PATH,
    ]
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(p) for p in outputs],
        "hashes_sha256": {
            **{str(p): sha256_file(p) for p in required_inputs},
            **{str(p): sha256_file(p) for p in outputs if p.exists() and p != OUTPUT_MANIFEST},
        },
    }
    write_json_strict(OUTPUT_MANIFEST, manifest)

    strict_targets = [OUTPUT_METRICS_SNAPSHOT, OUTPUT_PLOT_INVENTORY, OUTPUT_MANIFEST]
    g5 = True
    for target in strict_targets:
        try:
            parse_json_strict(target)
        except Exception:
            g5 = False
            break

    g6 = str(OUTPUT_MANIFEST) not in manifest.get("hashes_sha256", {})
    gx = OUTPUT_MANIFEST.exists()
    g4 = all(p.exists() for p in [OUTPUT_HTML, OUTPUT_REPORT, OUTPUT_METRICS_SNAPSHOT, OUTPUT_PLOT_INVENTORY, OUTPUT_MANIFEST])

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Scope",
        "- Plotly comparativo final Phase 2 com T044 (solution), T037 (meta), T039 (baseline), CDI e IBOV.",
        "",
        "## 2) Gates",
        f"- G1_INPUTS_PRESENT: {'PASS' if g1 else 'FAIL'}",
        f"- G2_COMMON_DATES_NONEMPTY: {'PASS' if g2 else 'FAIL'}",
        f"- G3_PLOT_BUILT: {'PASS' if g3 else 'FAIL'}",
        f"- G4_WRITE_ARTIFACTS: {'PASS' if g4 else 'FAIL'}",
        f"- G5_STRICT_JSON: {'PASS' if g5 else 'FAIL'}",
        f"- G6_MANIFEST_SELF_HASH_EXCLUDED: {'PASS' if g6 else 'FAIL'}",
        f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}",
        "",
        "## 3) Final equity normalized (base 100k)",
        f"- T044: {metrics_snapshot['final_equity_norm']['T044']:.2f}",
        f"- T037: {metrics_snapshot['final_equity_norm']['T037']:.2f}",
        f"- T039: {metrics_snapshot['final_equity_norm']['T039']:.2f}",
        f"- CDI : {metrics_snapshot['final_equity_norm']['CDI']:.2f}",
        f"- IBOV: {metrics_snapshot['final_equity_norm']['IBOV']:.2f}",
        "",
        "## 4) Beats check (T044 vs T037/T039)",
        f"- equity_final: vs T037={beats['equity_final']['vs_t037']} | vs T039={beats['equity_final']['vs_t039']}",
        f"- CAGR: vs T037={beats['cagr']['vs_t037']} | vs T039={beats['cagr']['vs_t039']}",
        f"- MDD: vs T037={beats['mdd']['vs_t037']} | vs T039={beats['mdd']['vs_t039']}",
        f"- Sharpe: vs T037={beats['sharpe']['vs_t037']} | vs T039={beats['sharpe']['vs_t039']}",
        "",
        "## 5) Artifacts",
        f"- {OUTPUT_HTML}",
        f"- {OUTPUT_REPORT}",
        f"- {OUTPUT_METRICS_SNAPSHOT}",
        f"- {OUTPUT_PLOT_INVENTORY}",
        f"- {OUTPUT_MANIFEST}",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines), encoding="utf-8")

    # Update manifest hash for report after final report write.
    manifest["hashes_sha256"][str(OUTPUT_REPORT)] = sha256_file(OUTPUT_REPORT)
    write_json_strict(OUTPUT_MANIFEST, manifest)
    g6 = str(OUTPUT_MANIFEST) not in manifest.get("hashes_sha256", {})

    print(f"- G4_WRITE_ARTIFACTS: {'PASS' if g4 else 'FAIL'}")
    print(f"- G5_STRICT_JSON: {'PASS' if g5 else 'FAIL'}")
    print(f"- G6_MANIFEST_SELF_HASH_EXCLUDED: {'PASS' if g6 else 'FAIL'}")
    print(f"- Gx_HASH_MANIFEST_PRESENT: {'PASS' if gx else 'FAIL'}")
    print("RETRY LOG: NONE")
    print("ARTIFACT LINKS:")
    print(f"- {OUTPUT_HTML}")
    print(f"- {OUTPUT_REPORT}")
    print(f"- {OUTPUT_METRICS_SNAPSHOT}")
    print(f"- {OUTPUT_PLOT_INVENTORY}")
    print(f"- {OUTPUT_MANIFEST}")

    ok = all([g1, g2, g3, g4, g5, g6, gx])
    print(f"OVERALL STATUS: [[ {'PASS' if ok else 'FAIL'} ]]")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
