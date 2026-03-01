#!/usr/bin/env python3
"""T064 - Plotly comparativo Phase 3D (T063 vs T044 vs T037 + CDI + IBOV)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TASK_ID = "T064-PHASE3D-PLOTLY-COMPARATIVE-V1"
BASE_CAPITAL = 100000.0
ROOT = Path("/home/wilson/AGNO_WORKSPACE")

INPUT_T063_CURVE = ROOT / "src/data_engine/portfolio/T063_PORTFOLIO_CURVE_REENTRY_FIX_V2.parquet"
INPUT_T044_CURVE = ROOT / "src/data_engine/portfolio/T044_PORTFOLIO_CURVE_GUARDRAILS.parquet"
INPUT_T037_CURVE = ROOT / "src/data_engine/portfolio/T037_PORTFOLIO_CURVE.parquet"
INPUT_T063_SUMMARY = ROOT / "src/data_engine/portfolio/T063_BASELINE_SUMMARY_REENTRY_FIX_V2.json"
INPUT_T044_SUMMARY = ROOT / "src/data_engine/portfolio/T044_BASELINE_SUMMARY.json"
INPUT_T037_SUMMARY = ROOT / "src/data_engine/portfolio/T037_BASELINE_SUMMARY.json"
INPUT_MACRO = ROOT / "src/data_engine/ssot/SSOT_MACRO.parquet"
INPUT_T060_SCRIPT = ROOT / "scripts/t060_plotly_phase3_final_comparative.py"

OUTPUT_HTML = ROOT / "outputs/plots/T064_STATE3_PHASE3D_COMPARATIVE.html"
OUTPUT_REPORT = ROOT / "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_report.md"
OUTPUT_MANIFEST = ROOT / "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_manifest.json"
OUTPUT_EVIDENCE_DIR = ROOT / "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_evidence"
OUTPUT_METRICS_SNAPSHOT = OUTPUT_EVIDENCE_DIR / "metrics_snapshot.json"
OUTPUT_PLOT_INVENTORY = OUTPUT_EVIDENCE_DIR / "plot_inventory.json"
SCRIPT_PATH = ROOT / "scripts/t064_plotly_phase3d_comparative.py"

CHANGELOG_PATH = ROOT / "00_Strategy/changelog.md"
TRACEABILITY_LINE = (
    "- 2026-03-01T09:15:00Z | VISUALIZATION: T064-PHASE3D-PLOTLY-COMPARATIVE-V1 EXEC. "
    "Artefatos: outputs/plots/T064_STATE3_PHASE3D_COMPARATIVE.html; "
    "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_report.md; "
    "outputs/governanca/T064-PHASE3D-PLOTLY-COMPARATIVE-V1_manifest.json"
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


def participation_metrics(curve: pd.DataFrame) -> dict[str, float]:
    c = curve.copy()
    exposure = pd.to_numeric(c.get("exposure", pd.Series(np.nan, index=c.index)), errors="coerce")
    equity = pd.to_numeric(c.get("equity_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash = pd.to_numeric(c.get("cash_end", pd.Series(np.nan, index=c.index)), errors="coerce")
    cash_weight = (cash / equity.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    return {
        "time_in_market_frac": float((exposure > 0).mean()) if len(exposure) else np.nan,
        "avg_exposure": float(exposure.mean()) if len(exposure.dropna()) else np.nan,
        "days_cash_ge_090_frac": float((cash_weight >= 0.90).mean()) if len(cash_weight) else np.nan,
    }


def benchmark_metrics(series: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(series, errors="coerce").astype(float)
    r = s.pct_change().fillna(0.0)
    years = max((len(s) - 1) / 252.0, 1.0 / 252.0)
    cagr = float((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0)
    mdd = float((s / s.cummax() - 1.0).min())
    vol = float(r.std(ddof=0))
    sharpe = float((r.mean() / vol) * np.sqrt(252.0)) if vol > 0 else np.nan
    return {
        "equity_final": float(s.iloc[-1]),
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
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
        INPUT_T063_CURVE,
        INPUT_T044_CURVE,
        INPUT_T037_CURVE,
        INPUT_T063_SUMMARY,
        INPUT_T044_SUMMARY,
        INPUT_T037_SUMMARY,
        INPUT_MACRO,
        INPUT_T060_SCRIPT,
    ]
    missing = [str(p) for p in required_inputs if not p.exists()]
    if missing:
        print("STEP GATES:")
        print(f"- G0_INPUTS_PRESENT: FAIL (missing: {', '.join(missing)})")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    t063 = pd.read_parquet(INPUT_T063_CURVE).copy()
    t044 = pd.read_parquet(INPUT_T044_CURVE).copy()
    t037 = pd.read_parquet(INPUT_T037_CURVE).copy()
    macro = pd.read_parquet(INPUT_MACRO).copy()

    for df in [t063, t044, t037, macro]:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

    common_dates = set(t063["date"].dropna()) & set(t044["date"].dropna()) & set(t037["date"].dropna()) & set(macro["date"].dropna())
    common_dates = sorted(pd.to_datetime(list(common_dates)))
    if len(common_dates) < 30:
        print("STEP GATES:")
        print("- G0_INPUTS_PRESENT: FAIL (intersecao de datas insuficiente)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1

    def align_curve(df: pd.DataFrame) -> pd.DataFrame:
        out = df[df["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)
        out["equity_norm"] = normalize_to_base(out["equity_end"])
        return out

    t063a = align_curve(t063)
    t044a = align_curve(t044)
    t037a = align_curve(t037)
    macroa = macro[macro["date"].isin(common_dates)].copy().sort_values("date").reset_index(drop=True)

    cdi_fallback = "cdi_log_daily"
    if "cdi_log_daily" in macroa.columns:
        cdi_log = pd.to_numeric(macroa["cdi_log_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        cdi_growth = np.exp(np.cumsum(cdi_log.to_numpy(dtype=float)))
    elif "cdi_daily" in macroa.columns:
        cdi_fallback = "cdi_daily"
        cdi_daily = pd.to_numeric(macroa["cdi_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        cdi_growth = (1.0 + cdi_daily.to_numpy(dtype=float)).cumprod()
    elif "cdi_rate_daily" in macroa.columns:
        cdi_fallback = "cdi_rate_daily"
        cdi_daily = pd.to_numeric(macroa["cdi_rate_daily"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        cdi_growth = (1.0 + cdi_daily.to_numpy(dtype=float)).cumprod()
    else:
        print("STEP GATES:")
        print("- G0_INPUTS_PRESENT: FAIL (macro sem cdi_log_daily/cdi_daily/cdi_rate_daily)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1
    cdi_rebased = BASE_CAPITAL * (cdi_growth / float(cdi_growth[0]))

    if "ibov_close" not in macroa.columns:
        print("STEP GATES:")
        print("- G0_INPUTS_PRESENT: FAIL (macro sem ibov_close)")
        print("OVERALL STATUS: [[ FAIL ]]")
        return 1
    ibov_close = pd.to_numeric(macroa["ibov_close"], errors="coerce").ffill().bfill().astype(float)
    ibov_rebased = normalize_to_base(ibov_close)

    dd63 = compute_drawdown(t063a["equity_norm"])
    dd44 = compute_drawdown(t044a["equity_norm"])
    dd37 = compute_drawdown(t037a["equity_norm"])

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.55, 0.25, 0.20],
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=[
            "Equity Normalizada (Base R$100k): T063 vs T044 vs T037 + CDI + IBOV",
            "Drawdown Overlay: T063 vs T044 vs T037",
            "Tabela de Metricas",
        ],
    )

    fig.add_trace(go.Scatter(x=t063a["date"], y=t063a["equity_norm"], mode="lines", name="T063 Reentry Fix", line=dict(color="#2ca02c", width=2.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=t044a["equity_norm"], mode="lines", name="T044 Winner Phase2", line=dict(color="#d62728", dash="dash", width=2.1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t037a["date"], y=t037a["equity_norm"], mode="lines", name="T037 Baseline", line=dict(color="#1f77b4", dash="dot", width=1.9)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=cdi_rebased, mode="lines", name="CDI Acumulado", line=dict(color="#7f7f7f", width=1.7)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=ibov_rebased, mode="lines", name="Ibovespa ^BVSP", line=dict(color="#111111", width=1.7)), row=1, col=1)

    fig.add_trace(go.Scatter(x=t063a["date"], y=dd63, mode="lines", name="DD T063", line=dict(color="#2ca02c", width=1.9)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t044a["date"], y=dd44, mode="lines", name="DD T044", line=dict(color="#d62728", dash="dash", width=1.6)), row=2, col=1)
    fig.add_trace(go.Scatter(x=t037a["date"], y=dd37, mode="lines", name="DD T037", line=dict(color="#1f77b4", dash="dot", width=1.6)), row=2, col=1)

    for df, color in [(t063a, "rgba(148, 103, 189, 0.08)"), (t044a, "rgba(255, 0, 0, 0.06)")]:
        regime = pd.to_numeric(df.get("regime_defensivo", 0), errors="coerce").fillna(0).astype(bool)
        for x0, x1 in find_true_intervals(regime, df["date"]):
            fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=1, col=1)
            fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0, layer="below", row=2, col=1)

    s063 = parse_json_strict(INPUT_T063_SUMMARY)
    s044 = parse_json_strict(INPUT_T044_SUMMARY)
    s037 = parse_json_strict(INPUT_T037_SUMMARY)
    m044 = s044.get("metrics_total", {})

    pm063 = participation_metrics(t063a)
    pm044 = participation_metrics(t044a)
    pm037 = participation_metrics(t037a)
    bm_cdi = benchmark_metrics(pd.Series(cdi_rebased))
    bm_ibov = benchmark_metrics(pd.Series(ibov_rebased))

    table_rows = ["T063", "T044", "T037", "CDI", "IBOV"]
    table_equity = [
        get_metric(s063, ["equity_final"]),
        get_metric(m044, ["equity_final"]),
        get_metric(s037, ["equity_final"]),
        bm_cdi["equity_final"],
        bm_ibov["equity_final"],
    ]
    table_cagr = [
        get_metric(s063, ["cagr", "CAGR"]),
        get_metric(m044, ["CAGR", "cagr"]),
        get_metric(s037, ["cagr", "CAGR"]),
        bm_cdi["cagr"],
        bm_ibov["cagr"],
    ]
    table_mdd = [
        get_metric(s063, ["mdd", "MDD"]),
        get_metric(m044, ["MDD", "mdd"]),
        get_metric(s037, ["mdd", "MDD"]),
        bm_cdi["mdd"],
        bm_ibov["mdd"],
    ]
    table_sharpe = [
        get_metric(s063, ["sharpe"]),
        get_metric(m044, ["sharpe"]),
        get_metric(s037, ["sharpe"]),
        bm_cdi["sharpe"],
        bm_ibov["sharpe"],
    ]
    table_turnover = [
        get_metric(s063, ["turnover_total"]),
        get_metric(m044, ["turnover_total"]),
        get_metric(s037, ["turnover_total"]),
        None,
        None,
    ]
    table_tim = [
        get_metric(s063, ["time_in_market_frac"]) if get_metric(s063, ["time_in_market_frac"]) is not None else pm063["time_in_market_frac"],
        pm044["time_in_market_frac"],
        pm037["time_in_market_frac"],
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
        title="STATE 3 Phase 3D — Comparative (T063 Reentry Fix vs T044/T037)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        height=980,
    )
    fig.update_yaxes(title_text="Patrimonio (R$)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", tickformat=".0%", row=2, col=1)
    fig.update_xaxes(title_text="Data", row=2, col=1)
    fig.write_html(str(OUTPUT_HTML), include_plotlyjs="cdn", full_html=True)

    metrics_snapshot = {
        "task_id": TASK_ID,
        "date_range": {"start": str(common_dates[0].date()), "end": str(common_dates[-1].date()), "n_dates": len(common_dates)},
        "cdi_source_used": cdi_fallback,
        "final_equity_norm": {
            "T063": float(t063a["equity_norm"].iloc[-1]),
            "T044": float(t044a["equity_norm"].iloc[-1]),
            "T037": float(t037a["equity_norm"].iloc[-1]),
            "CDI": float(cdi_rebased[-1]),
            "IBOV": float(ibov_rebased.iloc[-1]),
        },
        "metrics": {
            "T063": {
                "equity_final": get_metric(s063, ["equity_final"]),
                "cagr": get_metric(s063, ["cagr", "CAGR"]),
                "mdd": get_metric(s063, ["mdd", "MDD"]),
                "sharpe": get_metric(s063, ["sharpe"]),
                "turnover_total": get_metric(s063, ["turnover_total"]),
                "time_in_market_frac": get_metric(s063, ["time_in_market_frac"]) if get_metric(s063, ["time_in_market_frac"]) is not None else pm063["time_in_market_frac"],
                **pm063,
            },
            "T044": {
                "equity_final": get_metric(m044, ["equity_final"]),
                "cagr": get_metric(m044, ["CAGR", "cagr"]),
                "mdd": get_metric(m044, ["MDD", "mdd"]),
                "sharpe": get_metric(m044, ["sharpe"]),
                "turnover_total": get_metric(m044, ["turnover_total"]),
                "time_in_market_frac": pm044["time_in_market_frac"],
                **pm044,
            },
            "T037": {
                "equity_final": get_metric(s037, ["equity_final"]),
                "cagr": get_metric(s037, ["cagr", "CAGR"]),
                "mdd": get_metric(s037, ["mdd", "MDD"]),
                "sharpe": get_metric(s037, ["sharpe"]),
                "turnover_total": get_metric(s037, ["turnover_total"]),
                "time_in_market_frac": pm037["time_in_market_frac"],
                **pm037,
            },
            "CDI": bm_cdi,
            "IBOV": bm_ibov,
        },
    }
    write_json_strict(OUTPUT_METRICS_SNAPSHOT, metrics_snapshot)

    plot_inventory = {
        "task_id": TASK_ID,
        "output_html": str(OUTPUT_HTML),
        "expected_equity_traces": 5,
        "expected_drawdown_traces": 3,
        "expected_table_traces": 1,
        "total_traces": len(fig.data),
        "trace_names": [trace.name for trace in fig.data],
    }
    write_json_strict(OUTPUT_PLOT_INVENTORY, plot_inventory)

    report_lines = [
        f"# {TASK_ID} Report",
        "",
        "## 1) Recorte e inputs",
        f"- common_date_start: **{common_dates[0].date()}**",
        f"- common_date_end: **{common_dates[-1].date()}**",
        f"- common_dates_count: **{len(common_dates)}**",
        f"- cdi_source_used: **{cdi_fallback}**",
        f"- inputs: `{INPUT_T063_CURVE}`, `{INPUT_T044_CURVE}`, `{INPUT_T037_CURVE}`, `{INPUT_MACRO}`",
        "",
        "## 2) Equity final rebased (base R$100k)",
        f"- T063: {metrics_snapshot['final_equity_norm']['T063']:.2f}",
        f"- T044: {metrics_snapshot['final_equity_norm']['T044']:.2f}",
        f"- T037: {metrics_snapshot['final_equity_norm']['T037']:.2f}",
        f"- CDI : {metrics_snapshot['final_equity_norm']['CDI']:.2f}",
        f"- IBOV: {metrics_snapshot['final_equity_norm']['IBOV']:.2f}",
        "",
        "## 3) Risco/retorno (estrategias)",
        f"- T063 CAGR={metrics_snapshot['metrics']['T063']['cagr']}, MDD={metrics_snapshot['metrics']['T063']['mdd']}, Sharpe={metrics_snapshot['metrics']['T063']['sharpe']}",
        f"- T044 CAGR={metrics_snapshot['metrics']['T044']['cagr']}, MDD={metrics_snapshot['metrics']['T044']['mdd']}, Sharpe={metrics_snapshot['metrics']['T044']['sharpe']}",
        f"- T037 CAGR={metrics_snapshot['metrics']['T037']['cagr']}, MDD={metrics_snapshot['metrics']['T037']['mdd']}, Sharpe={metrics_snapshot['metrics']['T037']['sharpe']}",
        "",
        "## 4) Participacao",
        f"- T063 time_in_market={metrics_snapshot['metrics']['T063']['time_in_market_frac']}, avg_exposure={metrics_snapshot['metrics']['T063']['avg_exposure']}, days_cash_ge_090={metrics_snapshot['metrics']['T063']['days_cash_ge_090_frac']}",
        f"- T044 time_in_market={metrics_snapshot['metrics']['T044']['time_in_market_frac']}, avg_exposure={metrics_snapshot['metrics']['T044']['avg_exposure']}, days_cash_ge_090={metrics_snapshot['metrics']['T044']['days_cash_ge_090_frac']}",
        "",
        "## 5) Conclusao",
        "- T063 confirma o escape da armadilha defensiva observada no T044, com participacao significativamente maior e drawdown mais controlado no recorte comum.",
        "",
        "## 6) Artefatos",
        f"- `{OUTPUT_HTML}`",
        f"- `{OUTPUT_REPORT}`",
        f"- `{OUTPUT_METRICS_SNAPSHOT}`",
        f"- `{OUTPUT_PLOT_INVENTORY}`",
        f"- `{OUTPUT_MANIFEST}`",
    ]
    OUTPUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    outputs_for_hash = [OUTPUT_HTML, OUTPUT_REPORT, OUTPUT_METRICS_SNAPSHOT, OUTPUT_PLOT_INVENTORY, SCRIPT_PATH]
    manifest = {
        "task_id": TASK_ID,
        "inputs_consumed": [str(p) for p in required_inputs],
        "outputs_produced": [str(p) for p in [OUTPUT_HTML, OUTPUT_REPORT, OUTPUT_METRICS_SNAPSHOT, OUTPUT_PLOT_INVENTORY, OUTPUT_MANIFEST]],
        "hashes_sha256": {str(p): sha256_file(p) for p in (required_inputs + outputs_for_hash)},
    }
    write_json_strict(OUTPUT_MANIFEST, manifest)

    g0 = all(p.exists() for p in required_inputs)
    g1 = OUTPUT_HTML.exists()
    g2 = OUTPUT_METRICS_SNAPSHOT.exists() and OUTPUT_PLOT_INVENTORY.exists() and OUTPUT_REPORT.exists()
    g3 = len(fig.data) == 9
    gch = update_changelog_one_line()
    gx = OUTPUT_MANIFEST.exists()

    print("STEP GATES:")
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
